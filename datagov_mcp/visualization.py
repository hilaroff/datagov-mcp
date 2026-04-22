"""Visualization and data profiling tools for CKAN datasets.

Uses prefab-ui components to render interactive UI via MCP Apps.
"""

import html as html_lib
import json
from collections import Counter
from typing import Any

from fastmcp import Context
from prefab_ui.components import (
    H2,
    Column,
    DataTable,
    DataTableColumn,
    Embed,
    Metric,
    Row,
)
from prefab_ui.components.base import Component
from prefab_ui.components.charts import BarChart, ChartSeries, LineChart, ScatterChart
from prefab_ui.components.histogram import Histogram

from datagov_mcp.api import CKANAPIError, ckan_api_call
from datagov_mcp.apps import charts_app, maps_app, profile_app


def infer_field_type(values: list[Any]) -> str:
    """Infer the type of a field from sample values."""
    if not values:
        return "unknown"

    non_null = [v for v in values if v is not None]
    if not non_null:
        return "null"

    try:
        numeric_values = [float(v) for v in non_null if v != ""]
        if len(numeric_values) > len(non_null) * 0.8:
            if all(v == int(v) for v in numeric_values):
                return "integer"
            return "number"
    except (ValueError, TypeError):
        pass

    sample_str = str(non_null[0]).lower()
    if any(
        keyword in sample_str for keyword in ["lat", "latitude", "lng", "lon", "longitude", "coord"]
    ):
        return "coordinate"

    return "string"


def calculate_stats(values: list[Any], field_type: str) -> dict[str, Any]:
    """Calculate statistics for a field based on its type."""
    stats: dict[str, Any] = {
        "count": len(values),
        "null_count": sum(1 for v in values if v is None),
    }

    non_null = [v for v in values if v is not None]
    if not non_null:
        return stats

    if field_type in ["integer", "number"]:
        try:
            numeric = [float(v) for v in non_null if v != ""]
            if numeric:
                stats.update(
                    {
                        "min": min(numeric),
                        "max": max(numeric),
                        "mean": sum(numeric) / len(numeric),
                    }
                )
        except (ValueError, TypeError):
            pass
    elif field_type == "string":
        counter = Counter(str(v) for v in non_null)
        stats["unique_count"] = len(counter)
        stats["top_values"] = dict(counter.most_common(5))

    return stats


def _coerce_numeric(values: list[Any]) -> list[float]:
    """Coerce values to floats, skipping non-numeric entries."""
    result = []
    for v in values:
        try:
            result.append(float(v))
        except (ValueError, TypeError):
            continue
    return result


def _coerce_record_field(records: list[dict], field: str) -> list[dict]:
    """Coerce a field to float in-place across records, dropping invalid rows."""
    clean = []
    for r in records:
        try:
            r[field] = float(r[field])
            clean.append(r)
        except (ValueError, TypeError, KeyError):
            continue
    return clean


@profile_app.ui()
async def dataset_profile(ctx: Context, resource_id: str, sample_size: int = 100) -> Component:
    """
    Profile a dataset resource to understand its structure and data quality.

    Analyzes a sample of records to infer schema, detect missing values,
    calculate basic statistics, and identify data types.

    Args:
        resource_id: ID of the resource to profile
        sample_size: Number of records to sample (default: 100)
    """
    await ctx.info(f"Profiling resource: {resource_id}")

    try:
        result = await ckan_api_call(
            "datastore_search",
            params={"resource_id": resource_id, "limit": sample_size},
        )

        records = result.get("result", {}).get("records", [])
        fields = result.get("result", {}).get("fields", [])

        if not records:
            return Column(children=[H2("No records found in resource")])

        field_profiles = []
        for field_info in fields:
            field_name = field_info.get("id") or field_info.get("name", "")
            if field_name == "_id":
                continue

            values = [record.get(field_name) for record in records]
            field_type = infer_field_type(values)
            stats = calculate_stats(values, field_type)
            missingness = stats["null_count"] / stats["count"] if stats["count"] > 0 else 0

            row: dict[str, Any] = {
                "field": field_name,
                "type": field_type,
                "count": stats["count"],
                "nulls": stats["null_count"],
                "missingness": f"{missingness:.1%}",
            }
            if "min" in stats:
                row["min"] = stats["min"]
                row["max"] = stats["max"]
                row["mean"] = round(stats["mean"], 2)
            if "unique_count" in stats:
                row["unique"] = stats["unique_count"]

            field_profiles.append(row)

        metrics = Row(
            children=[
                Metric(label="Resource", value=resource_id[:16] + "..."),
                Metric(label="Sample Size", value=str(len(records))),
                Metric(label="Fields", value=str(len(field_profiles))),
            ]
        )

        columns = [
            DataTableColumn(key="field", header="Field"),
            DataTableColumn(key="type", header="Type"),
            DataTableColumn(key="count", header="Count"),
            DataTableColumn(key="nulls", header="Nulls"),
            DataTableColumn(key="missingness", header="Missing %"),
        ]
        if any("min" in fp for fp in field_profiles):
            columns.extend(
                [
                    DataTableColumn(key="min", header="Min"),
                    DataTableColumn(key="max", header="Max"),
                    DataTableColumn(key="mean", header="Mean"),
                ]
            )
        if any("unique" in fp for fp in field_profiles):
            columns.append(DataTableColumn(key="unique", header="Unique"))

        table = DataTable(columns=columns, rows=field_profiles, search=True)

        return Column(children=[H2("Dataset Profile"), metrics, table])

    except CKANAPIError as e:
        await ctx.error(f"Failed to profile dataset: {e.message}")
        return Column(children=[H2(f"Error: {e.message}")])


@charts_app.ui()
async def chart_generator(
    ctx: Context,
    resource_id: str,
    chart_type: str,
    x_field: str,
    y_field: str = "",
    title: str = "",
    limit: int = 100,
) -> Component:
    """
    Generate an interactive chart from a dataset resource.

    Supports histogram, bar, line, and scatter chart types using native
    prefab-ui components rendered via MCP Apps.

    Args:
        resource_id: ID of the resource to visualize
        chart_type: Type of chart ('histogram', 'bar', 'line', 'scatter')
        x_field: Field name for X-axis
        y_field: Field name for Y-axis (not needed for histogram)
        title: Chart title (optional)
        limit: Maximum number of records to visualize (default: 100)
    """
    await ctx.info(f"Generating {chart_type} chart for resource: {resource_id}")

    try:
        result = await ckan_api_call(
            "datastore_search",
            params={"resource_id": resource_id, "limit": limit},
        )

        records = result.get("result", {}).get("records", [])

        if not records:
            return Column(children=[H2("No records found in resource")])

        chart_title = title or f"{chart_type.capitalize()} Chart"
        heading = H2(chart_title)

        if chart_type == "histogram":
            values = _coerce_numeric([r.get(x_field) for r in records])
            if not values:
                return Column(children=[H2(f"No numeric values found in field '{x_field}'")])
            chart = Histogram(values=values, x_axis=x_field, height=400)

        elif chart_type == "bar":
            clean = _coerce_record_field([dict(r) for r in records], y_field)
            if not clean:
                return Column(children=[H2("No valid data for bar chart")])
            chart = BarChart(
                data=clean,
                series=[ChartSeries(data_key=y_field, label=y_field)],
                x_axis=x_field,
                height=400,
            )

        elif chart_type == "line":
            clean = _coerce_record_field([dict(r) for r in records], y_field)
            if not clean:
                return Column(children=[H2("No valid data for line chart")])
            clean.sort(key=lambda r: r.get(x_field, 0))
            chart = LineChart(
                data=clean,
                series=[ChartSeries(data_key=y_field, label=y_field)],
                x_axis=x_field,
                height=400,
            )

        elif chart_type == "scatter":
            clean = _coerce_record_field([dict(r) for r in records], y_field)
            clean = _coerce_record_field(clean, x_field)
            if not clean:
                return Column(children=[H2("No valid data for scatter chart")])
            chart = ScatterChart(
                data=clean,
                series=[ChartSeries(data_key=y_field, label=y_field)],
                x_axis=x_field,
                y_axis=y_field,
                height=400,
            )

        else:
            return Column(children=[H2(f"Unsupported chart type: {chart_type}")])

        return Column(children=[heading, chart])

    except CKANAPIError as e:
        await ctx.error(f"Failed to generate chart: {e.message}")
        return Column(children=[H2(f"Error: {e.message}")])


@maps_app.ui()
async def map_generator(
    ctx: Context, resource_id: str, lat_field: str, lon_field: str, limit: int = 500
) -> Component:
    """
    Generate an interactive map from geographic data.

    Creates a Leaflet map visualization for datasets with latitude/longitude
    coordinates, rendered via MCP Apps.

    Args:
        resource_id: ID of the resource to map
        lat_field: Field name containing latitude values
        lon_field: Field name containing longitude values
        limit: Maximum number of points to map (default: 500)
    """
    await ctx.info(f"Generating map for resource: {resource_id}")

    try:
        result = await ckan_api_call(
            "datastore_search",
            params={"resource_id": resource_id, "limit": limit},
        )

        records = result.get("result", {}).get("records", [])

        if not records:
            return Column(children=[H2("No records found in resource")])

        # Build GeoJSON with escaped popup content
        features = []
        for record in records:
            try:
                lat = float(record.get(lat_field, 0))
                lon = float(record.get(lon_field, 0))

                if lat and lon:
                    props = {
                        html_lib.escape(str(k)): html_lib.escape(str(v))
                        for k, v in record.items()
                        if k not in [lat_field, lon_field]
                    }
                    feature = {
                        "type": "Feature",
                        "geometry": {"type": "Point", "coordinates": [lon, lat]},
                        "properties": props,
                    }
                    features.append(feature)
            except (ValueError, TypeError):
                continue

        if not features:
            return Column(children=[H2("No valid geographic coordinates found")])

        geojson = {"type": "FeatureCollection", "features": features}

        lats = [f["geometry"]["coordinates"][1] for f in features]
        lons = [f["geometry"]["coordinates"][0] for f in features]
        center_lat = sum(lats) / len(lats)
        center_lon = sum(lons) / len(lons)

        map_html = f"""<!DOCTYPE html>
<html>
<head>
  <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
  <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
  <style>
    body {{ margin: 0; padding: 0; }}
    #map {{ height: 100vh; width: 100%; }}
  </style>
</head>
<body>
  <div id="map"></div>
  <script>
    var map = L.map('map').setView([{center_lat}, {center_lon}], 10);
    L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{
      attribution: '&copy; OpenStreetMap contributors'
    }}).addTo(map);

    var geojson = {json.dumps(geojson)};
    L.geoJSON(geojson, {{
      onEachFeature: function(feature, layer) {{
        if (feature.properties) {{
          var popup = Object.entries(feature.properties)
            .map(function(e) {{ return '<b>' + e[0] + '</b>: ' + e[1]; }})
            .join('<br>');
          layer.bindPopup(popup);
        }}
      }}
    }}).addTo(map);
  </script>
</body>
</html>"""

        return Embed(html=map_html, height="600px")

    except CKANAPIError as e:
        await ctx.error(f"Failed to generate map: {e.message}")
        return Column(children=[H2(f"Error: {e.message}")])

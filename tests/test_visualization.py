"""Tests for visualization and profiling tools."""

import pytest
import respx
from httpx import Response
from prefab_ui.components import DataTable, Embed
from prefab_ui.components.base import Component
from prefab_ui.components.charts import BarChart, LineChart, ScatterChart
from prefab_ui.components.histogram import Histogram

from datagov_mcp.api import BASE_URL
from datagov_mcp.visualization import chart_generator, dataset_profile, map_generator


class MockContext:
    """Mock Context for testing."""

    def __init__(self):
        self.info_messages = []
        self.error_messages = []

    async def info(self, message: str):
        self.info_messages.append(message)

    async def error(self, message: str):
        self.error_messages.append(message)


def _find_child(component, child_type):
    """Recursively find a child component of the given type."""
    if isinstance(component, child_type):
        return component
    if hasattr(component, "children"):
        for child in component.children or []:
            found = _find_child(child, child_type)
            if found:
                return found
    return None


@pytest.mark.asyncio
class TestVisualizationTools:
    """Test visualization and profiling tools."""

    @respx.mock
    async def test_dataset_profile(self):
        """Test dataset profiling tool returns Component with DataTable."""
        respx.get(f"{BASE_URL}/action/datastore_search").mock(
            return_value=Response(
                200,
                json={
                    "success": True,
                    "result": {
                        "records": [
                            {"_id": 1, "name": "Alice", "age": 30, "city": "Tel Aviv"},
                            {"_id": 2, "name": "Bob", "age": 25, "city": "Jerusalem"},
                            {"_id": 3, "name": "Charlie", "age": 35, "city": "Haifa"},
                        ],
                        "fields": [
                            {"id": "_id", "type": "int"},
                            {"id": "name", "type": "text"},
                            {"id": "age", "type": "int"},
                            {"id": "city", "type": "text"},
                        ],
                    },
                },
            )
        )

        ctx = MockContext()
        result = await dataset_profile(ctx, resource_id="test-resource", sample_size=10)

        assert isinstance(result, Component)

        # Should contain a DataTable with field info
        table = _find_child(result, DataTable)
        assert table is not None
        assert len(table.rows) == 3  # name, age, city (excluding _id)

        # Check age field is detected as integer
        age_row = next(r for r in table.rows if r["field"] == "age")
        assert age_row["type"] == "integer"

        # Check city field is detected as string
        city_row = next(r for r in table.rows if r["field"] == "city")
        assert city_row["type"] == "string"

    @respx.mock
    async def test_chart_generator_histogram(self):
        """Test histogram generation returns Histogram component."""
        respx.get(f"{BASE_URL}/action/datastore_search").mock(
            return_value=Response(
                200,
                json={
                    "success": True,
                    "result": {
                        "records": [
                            {"age": 20},
                            {"age": 25},
                            {"age": 30},
                            {"age": 35},
                            {"age": 40},
                        ],
                    },
                },
            )
        )

        ctx = MockContext()
        result = await chart_generator(
            ctx,
            resource_id="test-resource",
            chart_type="histogram",
            x_field="age",
            title="Age Distribution",
        )

        assert isinstance(result, Component)
        hist = _find_child(result, Histogram)
        assert hist is not None
        assert hist.values == [20.0, 25.0, 30.0, 35.0, 40.0]

    @respx.mock
    async def test_chart_generator_bar(self):
        """Test bar chart generation returns BarChart component."""
        respx.get(f"{BASE_URL}/action/datastore_search").mock(
            return_value=Response(
                200,
                json={
                    "success": True,
                    "result": {
                        "records": [
                            {"city": "Tel Aviv", "population": 460000},
                            {"city": "Jerusalem", "population": 936000},
                            {"city": "Haifa", "population": 285000},
                        ],
                    },
                },
            )
        )

        ctx = MockContext()
        result = await chart_generator(
            ctx,
            resource_id="test-resource",
            chart_type="bar",
            x_field="city",
            y_field="population",
        )

        assert isinstance(result, Component)
        bar = _find_child(result, BarChart)
        assert bar is not None
        assert bar.x_axis == "city"
        assert len(bar.data) == 3

    @respx.mock
    async def test_chart_generator_line(self):
        """Test line chart generation returns LineChart component."""
        respx.get(f"{BASE_URL}/action/datastore_search").mock(
            return_value=Response(
                200,
                json={
                    "success": True,
                    "result": {
                        "records": [
                            {"year": 2020, "value": 100},
                            {"year": 2021, "value": 150},
                            {"year": 2022, "value": 200},
                        ],
                    },
                },
            )
        )

        ctx = MockContext()
        result = await chart_generator(
            ctx,
            resource_id="test-resource",
            chart_type="line",
            x_field="year",
            y_field="value",
        )

        assert isinstance(result, Component)
        line = _find_child(result, LineChart)
        assert line is not None
        assert line.x_axis == "year"

    @respx.mock
    async def test_chart_generator_scatter(self):
        """Test scatter chart generation returns ScatterChart component."""
        respx.get(f"{BASE_URL}/action/datastore_search").mock(
            return_value=Response(
                200,
                json={
                    "success": True,
                    "result": {
                        "records": [
                            {"x": 1, "y": 10},
                            {"x": 2, "y": 20},
                            {"x": 3, "y": 30},
                        ],
                    },
                },
            )
        )

        ctx = MockContext()
        result = await chart_generator(
            ctx,
            resource_id="test-resource",
            chart_type="scatter",
            x_field="x",
            y_field="y",
        )

        assert isinstance(result, Component)
        scatter = _find_child(result, ScatterChart)
        assert scatter is not None

    @respx.mock
    async def test_map_generator(self):
        """Test map generation returns Embed component with Leaflet HTML."""
        respx.get(f"{BASE_URL}/action/datastore_search").mock(
            return_value=Response(
                200,
                json={
                    "success": True,
                    "result": {
                        "records": [
                            {
                                "name": "Tel Aviv",
                                "latitude": 32.0853,
                                "longitude": 34.7818,
                                "population": 460000,
                            },
                            {
                                "name": "Jerusalem",
                                "latitude": 31.7683,
                                "longitude": 35.2137,
                                "population": 936000,
                            },
                            {
                                "name": "Haifa",
                                "latitude": 32.7940,
                                "longitude": 34.9896,
                                "population": 285000,
                            },
                        ],
                    },
                },
            )
        )

        ctx = MockContext()
        result = await map_generator(
            ctx,
            resource_id="test-resource",
            lat_field="latitude",
            lon_field="longitude",
            limit=100,
        )

        assert isinstance(result, Embed)
        assert result.html is not None
        assert "leaflet" in result.html.lower()
        assert "FeatureCollection" in result.html
        # Verify all 3 points are in the GeoJSON
        assert "Tel Aviv" in result.html
        assert "Jerusalem" in result.html
        assert "Haifa" in result.html

    @respx.mock
    async def test_map_generator_no_valid_coordinates(self):
        """Test map generation with invalid coordinates returns error UI."""
        respx.get(f"{BASE_URL}/action/datastore_search").mock(
            return_value=Response(
                200,
                json={
                    "success": True,
                    "result": {
                        "records": [
                            {"name": "Invalid", "lat": "not-a-number", "lon": "invalid"},
                        ],
                    },
                },
            )
        )

        ctx = MockContext()
        result = await map_generator(
            ctx, resource_id="test-resource", lat_field="lat", lon_field="lon"
        )

        assert isinstance(result, Component)

    @respx.mock
    async def test_chart_generator_unsupported_type(self):
        """Test chart generation with unsupported chart type returns error UI."""
        respx.get(f"{BASE_URL}/action/datastore_search").mock(
            return_value=Response(
                200,
                json={
                    "success": True,
                    "result": {"records": [{"x": 1, "y": 2}]},
                },
            )
        )

        ctx = MockContext()
        result = await chart_generator(
            ctx,
            resource_id="test-resource",
            chart_type="invalid-type",
            x_field="x",
            y_field="y",
        )

        assert isinstance(result, Component)

    @respx.mock
    async def test_chart_generator_coerces_string_values(self):
        """Test that string numeric values are properly coerced."""
        respx.get(f"{BASE_URL}/action/datastore_search").mock(
            return_value=Response(
                200,
                json={
                    "success": True,
                    "result": {
                        "records": [
                            {"age": "20"},
                            {"age": "25"},
                            {"age": "30"},
                        ],
                    },
                },
            )
        )

        ctx = MockContext()
        result = await chart_generator(
            ctx,
            resource_id="test-resource",
            chart_type="histogram",
            x_field="age",
        )

        assert isinstance(result, Component)
        hist = _find_child(result, Histogram)
        assert hist is not None
        assert hist.values == [20.0, 25.0, 30.0]

    @respx.mock
    async def test_map_generator_escapes_html_in_popups(self):
        """Test that map popup values are HTML-escaped to prevent XSS."""
        respx.get(f"{BASE_URL}/action/datastore_search").mock(
            return_value=Response(
                200,
                json={
                    "success": True,
                    "result": {
                        "records": [
                            {
                                "name": "<script>alert('xss')</script>",
                                "lat": 32.0853,
                                "lon": 34.7818,
                            },
                        ],
                    },
                },
            )
        )

        ctx = MockContext()
        result = await map_generator(
            ctx, resource_id="test-resource", lat_field="lat", lon_field="lon"
        )

        assert isinstance(result, Embed)
        # Raw script tag should not appear in the HTML
        assert "<script>alert" not in result.html
        assert "&lt;script&gt;" in result.html

"""Coordinate normalization helpers for data.gov.il resources.

Many data.gov.il resources publish coordinates in Israeli ITM (EPSG:2039)
meters rather than WGS84 degrees. The host app's MCP-to-map pipeline only
plots points from fields named exactly lat/latitude/y or
lon/lng/long/longitude/x whose values fall within valid WGS84 bounds — ITM
values (large, Israel-specific meter offsets) are silently ignored unless
converted to real latitude/longitude first, which is what this module does.
"""

from typing import Any

from pyproj import Transformer

ITM_EPSG = "EPSG:2039"
WGS84_EPSG = "EPSG:4326"

_itm_to_wgs84 = Transformer.from_crs(ITM_EPSG, WGS84_EPSG, always_xy=True)

# Candidate field names, matched case-insensitively with "_"/"-" stripped
# (so "X-utm", "ITM_X", "x_utm" and "x" all match the same candidate set).
_X_KEYS = {"x", "itmx", "east", "easting", "xutm"}
_Y_KEYS = {"y", "itmy", "north", "northing", "yutm"}
_LON_KEYS = {"lon", "long", "longitude", "lng"}
_LAT_KEYS = {"lat", "latitude"}

# Generous bounding box for Israel in ITM meters (EPSG:2039). Real ITM
# coordinates anywhere in the country fall comfortably within this range,
# and it's far outside valid WGS84 degree values so there's no ambiguity.
_ITM_X_RANGE = (0.0, 400_000.0)
_ITM_Y_RANGE = (200_000.0, 1_300_000.0)


def _normalize_key(key: str) -> str:
    return key.lower().replace("_", "").replace("-", "")


def _find_key(record: dict[str, Any], candidates: set[str]) -> str | None:
    for key in record:
        if _normalize_key(key) in candidates:
            return key
    return None


def _looks_like_itm(x: float, y: float) -> bool:
    return _ITM_X_RANGE[0] <= x <= _ITM_X_RANGE[1] and _ITM_Y_RANGE[0] <= y <= _ITM_Y_RANGE[1]


def _looks_like_wgs84(lon: float, lat: float) -> bool:
    return abs(lat) <= 90 and abs(lon) <= 180


def enrich_record_with_coordinates(record: dict[str, Any]) -> dict[str, Any]:
    """
    Add clean WGS84 latitude/longitude fields to a record, in place.

    Looks for a lon/lat pair first, then a generic X/Y (or ITM_X/ITM_Y,
    X-utm/Y-utm, etc.) pair. If the values already look like valid WGS84
    degrees they're used as-is; if they look like Israeli ITM meters
    they're converted via EPSG:2039 -> EPSG:4326. Leaves the record
    untouched if no usable coordinate pair is found.

    Args:
        record: A single datastore record (mutated and returned).

    Returns:
        The same record dict, with "latitude"/"longitude" added if resolved.
    """
    lon_key = _find_key(record, _LON_KEYS)
    lat_key = _find_key(record, _LAT_KEYS)
    x_key = _find_key(record, _X_KEYS)
    y_key = _find_key(record, _Y_KEYS)

    try:
        if lon_key and lat_key:
            lon, lat = float(record[lon_key]), float(record[lat_key])
            if _looks_like_wgs84(lon, lat):
                record["latitude"] = round(lat, 6)
                record["longitude"] = round(lon, 6)
                return record

        if x_key and y_key:
            x, y = float(record[x_key]), float(record[y_key])
            if _looks_like_wgs84(x, y):
                # Generic X/Y naming but values are already WGS84-ish degrees.
                record["latitude"] = round(y, 6)
                record["longitude"] = round(x, 6)
            elif _looks_like_itm(x, y):
                lon, lat = _itm_to_wgs84.transform(x, y)
                record["latitude"] = round(lat, 6)
                record["longitude"] = round(lon, 6)
    except (TypeError, ValueError):
        pass

    return record

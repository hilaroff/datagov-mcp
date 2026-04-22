"""MCP Apps definitions for visualization tools.

Each FastMCPApp groups related UI tools together. The apps are registered
as providers on the main FastMCP server in server.py.
"""

from fastmcp import FastMCPApp

profile_app = FastMCPApp("DataProfile")
charts_app = FastMCPApp("Charts")

# Map app needs CSP for Leaflet CDN and OpenStreetMap tile servers
maps_app = FastMCPApp("Maps")

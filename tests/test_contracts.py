"""Contract tests for MCP tools - ensures API stability."""

import pytest
from fastmcp import FastMCP

from datagov_mcp.server import mcp


class TestToolContracts:
    """Test that tool names and parameters remain stable."""

    def test_server_is_fastmcp_instance(self):
        """Verify server is a FastMCP instance."""
        assert isinstance(mcp, FastMCP)
        assert mcp.name == "DataGovIL"

    @pytest.mark.asyncio
    async def test_all_tools_exist(self):
        """Verify all expected tools are registered."""
        expected_tools = [
            "status_show",
            "license_list",
            "package_list",
            "package_search",
            "package_show",
            "organization_list",
            "organization_show",
            "resource_search",
            "datastore_search",
            "fetch_data",
            "dataset_profile",
            "chart_generator",
            "map_generator",
        ]

        tools = await mcp.list_tools()
        tool_names = [t.name for t in tools]
        for tool_name in expected_tools:
            assert tool_name in tool_names, f"Tool {tool_name} not found"

    @pytest.mark.asyncio
    async def test_status_show_signature(self):
        """Verify status_show tool signature."""
        tools = await mcp.list_tools()
        tool = next((t for t in tools if t.name == "status_show"), None)
        assert tool is not None
        assert "Get the CKAN version" in tool.description

    @pytest.mark.asyncio
    async def test_package_search_signature(self):
        """Verify package_search tool has expected parameters."""
        tools = await mcp.list_tools()
        tool = next((t for t in tools if t.name == "package_search"), None)
        assert tool is not None

        # Check parameter names exist in the schema
        schema = tool.parameters
        props = schema.get("properties", {})

        expected_params = ["q", "fq", "sort", "rows", "start", "include_private"]
        for param in expected_params:
            assert param in props, f"Parameter {param} not found in package_search"

    @pytest.mark.asyncio
    async def test_package_show_signature(self):
        """Verify package_show requires 'id' parameter."""
        tools = await mcp.list_tools()
        tool = next((t for t in tools if t.name == "package_show"), None)
        assert tool is not None

        schema = tool.parameters
        required = schema.get("required", [])
        assert "id" in required, "package_show should require 'id' parameter"

    @pytest.mark.asyncio
    async def test_datastore_search_signature(self):
        """Verify datastore_search tool has expected parameters."""
        tools = await mcp.list_tools()
        tool = next((t for t in tools if t.name == "datastore_search"), None)
        assert tool is not None

        schema = tool.parameters
        props = schema.get("properties", {})
        required = schema.get("required", [])

        assert "resource_id" in required
        assert "limit" in props
        assert "offset" in props

    @pytest.mark.asyncio
    async def test_fetch_data_signature(self):
        """Verify fetch_data tool signature."""
        tools = await mcp.list_tools()
        tool = next((t for t in tools if t.name == "fetch_data"), None)
        assert tool is not None

        schema = tool.parameters
        required = schema.get("required", [])
        assert "dataset_name" in required

    @pytest.mark.asyncio
    async def test_visualization_tools_have_app_metadata(self):
        """Verify visualization tools are registered as MCP Apps with proper UI metadata."""
        tools = await mcp.list_tools()
        app_tool_names = ["dataset_profile", "chart_generator", "map_generator"]

        for name in app_tool_names:
            tool = next((t for t in tools if t.name == name), None)
            assert tool is not None, f"Tool {name} not found"
            assert tool.meta is not None, f"Tool {name} should have meta"
            ui_meta = tool.meta.get("ui")
            assert ui_meta is not None, f"Tool {name} should have ui metadata"
            assert isinstance(ui_meta, dict), f"Tool {name} ui metadata should be a dict"
            assert "resourceUri" in ui_meta, f"Tool {name} should have resourceUri in ui metadata"

    @pytest.mark.asyncio
    async def test_non_viz_tools_are_not_apps(self):
        """Verify non-visualization tools are NOT marked as apps."""
        tools = await mcp.list_tools()
        non_app_tools = ["status_show", "package_list", "package_search", "fetch_data"]

        for name in non_app_tools:
            tool = next((t for t in tools if t.name == name), None)
            assert tool is not None, f"Tool {name} not found"
            assert not tool.meta or not tool.meta.get("ui"), f"Tool {name} should not be an app"

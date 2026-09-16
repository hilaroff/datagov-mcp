"""Main MCP server implementation with CKAN tools."""

from fastmcp import Context, FastMCP

from datagov_mcp.api import CKANAPIError, ckan_api_call
from datagov_mcp.geo import enrich_record_with_coordinates

# Create an MCP server
mcp = FastMCP("DataGovIL")

# Import visualization tools (registers @app.ui() functions) and add app providers
from datagov_mcp import visualization  # noqa: E402, F401
from datagov_mcp.apps import charts_app, maps_app, profile_app  # noqa: E402

mcp.add_provider(profile_app)
mcp.add_provider(charts_app)
mcp.add_provider(maps_app)


@mcp.tool()
async def status_show(ctx: Context) -> dict:
    """Get the CKAN version and a list of installed extensions."""
    await ctx.info("Fetching CKAN status...")
    try:
        return await ckan_api_call("status_show", method="POST")
    except CKANAPIError as e:
        await ctx.error(f"Failed to fetch status: {e.message}")
        raise


@mcp.tool()
async def license_list(ctx: Context) -> dict:
    """Get the list of licenses available for datasets on the site."""
    await ctx.info("Fetching license list...")
    try:
        return await ckan_api_call("license_list")
    except CKANAPIError as e:
        await ctx.error(f"Failed to fetch licenses: {e.message}")
        raise


@mcp.tool()
async def package_list(ctx: Context) -> dict:
    """Get a list of all package IDs (datasets)."""
    await ctx.info("Fetching package list...")
    try:
        return await ckan_api_call("package_list")
    except CKANAPIError as e:
        await ctx.error(f"Failed to fetch packages: {e.message}")
        raise


@mcp.tool()
async def package_search(
    ctx: Context,
    q: str = "",
    fq: str = "",
    sort: str = "",
    rows: int = 20,
    start: int = 0,
    include_private: bool = False,
) -> dict:
    """
    Find packages (datasets) matching query terms.

    Args:
        q: Query string to search for
        fq: Filter query in SOLR format
        sort: Sorting order (e.g., 'metadata_modified desc')
        rows: Number of results to return (default: 20)
        start: Starting index for pagination (default: 0)
        include_private: Include private datasets (default: False)

    Returns:
        Search results with matching packages
    """
    await ctx.info("Searching for packages...")
    try:
        params = {
            "q": q,
            "fq": fq,
            "sort": sort,
            "rows": rows,
            "start": start,
            "include_private": include_private,
        }
        return await ckan_api_call("package_search", params=params)
    except CKANAPIError as e:
        await ctx.error(f"Failed to search packages: {e.message}")
        raise


@mcp.tool()
async def package_show(ctx: Context, id: str) -> dict:
    """
    Get metadata about one specific package (dataset).

    Args:
        id: The ID or name of the package

    Returns:
        Complete package metadata including resources
    """
    await ctx.info(f"Fetching metadata for package: {id}")
    try:
        return await ckan_api_call("package_show", params={"id": id})
    except CKANAPIError as e:
        await ctx.error(f"Failed to fetch package: {e.message}")
        raise


@mcp.tool()
async def organization_list(ctx: Context) -> dict:
    """Get names of all organizations."""
    await ctx.info("Fetching organization list...")
    try:
        return await ckan_api_call("organization_list")
    except CKANAPIError as e:
        await ctx.error(f"Failed to fetch organizations: {e.message}")
        raise


@mcp.tool()
async def organization_show(ctx: Context, id: str) -> dict:
    """
    Get details of a specific organization.

    Args:
        id: The ID or name of the organization

    Returns:
        Organization details including datasets
    """
    await ctx.info(f"Fetching details for organization: {id}")
    try:
        return await ckan_api_call("organization_show", params={"id": id})
    except CKANAPIError as e:
        await ctx.error(f"Failed to fetch organization: {e.message}")
        raise


@mcp.tool()
async def resource_search(
    ctx: Context,
    query: str = "",
    order_by: str = "",
    offset: int = 0,
    limit: int = 100,
) -> dict:
    """
    Find resources based on their field values.

    Args:
        query: Query string in SOLR format (e.g., 'name:data')
        order_by: Field to order by
        offset: Starting index for pagination
        limit: Maximum number of results

    Returns:
        Search results with matching resources
    """
    await ctx.info("Searching for resources...")
    try:
        params = {
            "query": query,
            "order_by": order_by,
            "offset": offset,
            "limit": limit,
        }
        return await ckan_api_call("resource_search", params=params)
    except CKANAPIError as e:
        await ctx.error(f"Failed to search resources: {e.message}")
        raise


@mcp.tool()
async def datastore_search(
    ctx: Context,
    resource_id: str,
    q: str = "",
    distinct: bool = False,
    plain: bool = True,
    limit: int = 100,
    offset: int = 0,
    fields: str = "",
    sort: str = "",
    include_total: bool = True,
    records_format: str = "objects",
) -> dict:
    """
    Search a datastore resource.

    Args:
        resource_id: ID of the resource to search
        q: Full-text query string
        distinct: Return only distinct results
        plain: Use plain text search (vs. PostgreSQL full-text)
        limit: Maximum number of records to return
        offset: Starting index for pagination
        fields: Comma-separated list of fields to return
        sort: Comma-separated list of fields to sort by
        include_total: Include total result count
        records_format: Format of records ('objects', 'lists', or 'csv')

    Returns:
        Datastore search results with records
    """
    await ctx.info(f"Searching datastore for resource: {resource_id}")
    try:
        params = {
            "resource_id": resource_id,
            "q": q,
            "distinct": distinct,
            "plain": plain,
            "limit": limit,
            "offset": offset,
            "fields": fields,
            "sort": sort,
            "include_total": include_total,
            "records_format": records_format,
        }
        return await ckan_api_call("datastore_search", params=params)
    except CKANAPIError as e:
        await ctx.error(f"Failed to search datastore: {e.message}")
        raise


@mcp.tool()
async def fetch_data(
    ctx: Context,
    dataset_name: str,
    limit: int = 100,
    offset: int = 0,
) -> dict:
    """
    Fetch data from public API based on a dataset name query.

    This is a convenience tool that combines package_show and datastore_search.
    It finds the first resource of a dataset and returns its data.

    Args:
        dataset_name: Name or ID of the dataset
        limit: Number of records to fetch
        offset: Starting index for pagination

    Returns:
        Records from the first resource of the dataset
    """
    await ctx.info(f"Fetching data for dataset: {dataset_name}")
    try:
        # First, get the dataset metadata
        package_data = await ckan_api_call("package_show", params={"id": dataset_name})
        resources = package_data.get("result", {}).get("resources", [])

        if not resources:
            return {"error": f"No resources found in dataset '{dataset_name}'"}

        # Use the first resource
        resource_id = resources[0]["id"]
        await ctx.info(f"Using resource: {resource_id}")

        # Fetch data from the datastore
        result = await ckan_api_call(
            "datastore_search",
            params={
                "resource_id": resource_id,
                "limit": limit,
                "offset": offset,
            },
        )

        # Return just the records for convenience
        if result.get("success"):
            return {"records": result["result"]["records"], "resource_id": resource_id}
        else:
            return {"error": "Failed to fetch data from datastore"}

    except CKANAPIError as e:
        await ctx.error(f"Failed to fetch data: {e.message}")
        return {"error": str(e.message)}


@mcp.tool()
async def find_and_query_dataset(
    ctx: Context,
    topic: str,
    filter_text: str = "",
    limit: int = 50,
) -> dict:
    """
    Search data.gov.il by topic and query its data table in one call — no resource_id needed.

    Use this as the DEFAULT tool whenever the user asks a natural-language question about
    a subject (e.g. "public transit stations", "תחנות תחבורה ציבורית", "air quality
    monitoring") without already knowing a specific resource_id. It searches CKAN packages
    by topic, re-ranks candidates by title-word overlap with the topic (CKAN's own
    relevance ranking is unreliable for compound Hebrew phrases — the exact phrase
    "תחנות תחבורה ציבורית" ranks its own matching dataset 10th out of 42 by default),
    picks the best-matching result that has a queryable datastore resource, then runs a
    full-text query against it (optionally filtered, e.g. by city name).

    Every returned record is also enriched with clean "latitude"/"longitude" WGS84 fields
    when a recognizable coordinate pair is found (lon/lat, or generic X/Y, ITM_X/ITM_Y,
    X-utm/Y-utm, etc.) — converting from Israeli ITM (EPSG:2039) meters if needed — so
    results can be plotted directly on a map without any manual coordinate handling.

    Args:
        topic: What kind of data to find, in Hebrew or English, e.g. "תחנות תחבורה ציבורית".
        filter_text: Optional full-text filter within the resource's records, e.g. a city
            name like "אבו גוש". Leave empty to return unfiltered records.
        limit: Maximum number of records to return (default: 50).

    Returns:
        Dict with the matched dataset/resource info and the enriched records, or an
        "error"/"candidate_datasets" payload if no queryable resource could be found.
    """
    await ctx.info(f"Searching datasets for topic: {topic}")
    try:
        search_result = await ckan_api_call("package_search", params={"q": topic, "rows": 20})
        packages = search_result.get("result", {}).get("results", [])

        if not packages:
            return {"error": f"No datasets found for topic '{topic}'"}

        # CKAN's relevance ranking is unreliable for multi-word Hebrew phrases, so
        # re-rank candidates locally by how many topic words appear in the title
        # (stable sort keeps CKAN's own order as the tiebreak).
        topic_words = [w for w in topic.strip().split() if w]

        def _title_match_score(pkg: dict) -> int:
            title = pkg.get("title") or ""
            return sum(1 for w in topic_words if w in title)

        packages = sorted(packages, key=_title_match_score, reverse=True)

        chosen_resource = None
        chosen_package = None
        for pkg in packages:
            for res in pkg.get("resources", []):
                if res.get("datastore_active"):
                    chosen_resource = res
                    chosen_package = pkg
                    break
            if chosen_resource:
                break

        if not chosen_resource:
            return {
                "error": (
                    f"Found {len(packages)} dataset(s) for '{topic}' but none have a "
                    "queryable data table (datastore). Try package_show on one of these "
                    "to inspect its resources manually."
                ),
                "candidate_datasets": [
                    {"id": pkg.get("name"), "title": pkg.get("title")} for pkg in packages
                ],
            }

        resource_id = chosen_resource["id"]
        await ctx.info(
            f"Using dataset '{chosen_package.get('title')}', "
            f"resource '{chosen_resource.get('name')}' ({resource_id})"
        )

        search_params: dict[str, object] = {"resource_id": resource_id, "limit": limit}
        if filter_text:
            search_params["q"] = filter_text

        datastore_result = await ckan_api_call("datastore_search", params=search_params)
        result = datastore_result.get("result", {})
        records = result.get("records", [])
        fields = result.get("fields", [])

        enriched_records = [enrich_record_with_coordinates(dict(r)) for r in records]
        geolocated_count = sum(1 for r in enriched_records if "latitude" in r)

        return {
            "dataset_title": chosen_package.get("title"),
            "resource_id": resource_id,
            "resource_name": chosen_resource.get("name"),
            "fields": [f.get("id") for f in fields if f.get("id") != "_id"],
            "total_matching_records": result.get("total"),
            "records_returned": len(enriched_records),
            "records_with_coordinates": geolocated_count,
            "records": enriched_records,
        }

    except CKANAPIError as e:
        await ctx.error(f"Failed to search/query dataset: {e.message}")
        return {"error": e.message}

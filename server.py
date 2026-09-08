"""MCP server exposing Metabase browse/query tools to Claude."""

from typing import Any

from mcp.server.fastmcp import FastMCP

from metabase_client import MetabaseClient

mcp = FastMCP("Metabase")

_client: MetabaseClient | None = None


def get_client() -> MetabaseClient:
    global _client
    if _client is None:
        _client = MetabaseClient()
    return _client


@mcp.tool()
def search(query: str, models: list[str] | None = None) -> Any:
    """
    Search across all Metabase items: dashboards, saved questions (cards),
    collections, databases, and tables.

    Args:
        query: Free-text search string.
        models: Optional filter, e.g. ["dashboard", "card"]. Omit to search everything.
    """
    return get_client().search(query, models)


@mcp.tool()
def list_databases() -> Any:
    """List all databases connected to this Metabase instance."""
    return get_client().list_databases()


@mcp.tool()
def list_tables(database_id: int) -> Any:
    """
    List all tables (with schema/field metadata) for a given database.

    Args:
        database_id: The Metabase database ID, from list_databases().
    """
    return get_client().list_tables(database_id)


@mcp.tool()
def list_collections() -> Any:
    """List all collections (folders of dashboards/cards) in this Metabase instance."""
    return get_client().list_collections()


@mcp.tool()
def get_dashboard(dashboard_id: int) -> Any:
    """
    Get the full definition of a dashboard, including its cards.

    Args:
        dashboard_id: The Metabase dashboard ID, from search() or list_collections().
    """
    return get_client().get_dashboard(dashboard_id)


@mcp.tool()
def get_card(card_id: int) -> Any:
    """
    Get the definition of a saved question (card) - its query, not its result data.

    Args:
        card_id: The Metabase card ID, from search().
    """
    return get_client().get_card(card_id)


@mcp.tool()
def run_card(card_id: int, parameters: list[dict[str, Any]] | None = None) -> Any:
    """
    Run an existing saved question (card) and return its result data.

    Args:
        card_id: The Metabase card ID to execute.
        parameters: Optional list of Metabase parameter objects to filter the card's query.
    """
    return get_client().run_card(card_id, parameters)


@mcp.tool()
def run_sql(database_id: int, sql: str) -> Any:
    """
    Run a read-only SQL query against a Metabase database. Only SELECT and
    WITH...SELECT statements are allowed - anything else is rejected before
    it reaches Metabase.

    Args:
        database_id: The Metabase database ID to query, from list_databases().
        sql: The SQL SELECT statement to run.
    """
    return get_client().run_sql(database_id, sql)


if __name__ == "__main__":
    mcp.run()

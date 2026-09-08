"""Smoke test that server.py registers the expected MCP tools."""

import asyncio

import server


def test_all_expected_tools_are_registered():
    tools = asyncio.run(server.mcp.list_tools())
    tool_names = {tool.name for tool in tools}

    assert tool_names == {
        "search",
        "list_databases",
        "list_tables",
        "list_collections",
        "get_dashboard",
        "get_card",
        "run_card",
        "run_sql",
    }

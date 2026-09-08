# Metabase MCP Server

An original [MCP (Model Context Protocol)](https://modelcontextprotocol.io) server
giving Claude read-only access to a Metabase instance: search dashboards/cards/
collections, browse databases and tables, run existing saved questions, and run
ad hoc read-only SQL.

## Tools

| Tool | Description |
|------|-------------|
| `search` | Search across dashboards, saved questions, collections, databases, tables |
| `list_databases` | List all databases connected to this Metabase instance |
| `list_tables` | List tables + field metadata for a database |
| `list_collections` | List all collections |
| `get_dashboard` | Get a dashboard's full definition |
| `get_card` | Get a saved question's definition (not its data) |
| `run_card` | Execute an existing saved question |
| `run_sql` | Run a read-only SQL query (SELECT / WITH...SELECT only — anything else is rejected before it reaches Metabase) |

## Setup

### Prerequisites

- Python 3.10+
- A Metabase account (API key, or LDAP email + password)

### Install

```bash
cd .claude/mcp/metabase-mcp
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # then fill in your Metabase URL + credentials
```

### Run the tests

```bash
pytest
```

### Register with Claude Code

Once `.env` has your real Metabase URL and credentials (see Install above), register the server pointing at this project's own venv interpreter — not the system `python3`, which won't have the dependencies installed:

```bash
claude mcp add metabase-own --scope local \
  -- "/Users/aakashsrivastava/Documents/PolicyBazaar Claude/.claude/mcp/metabase-mcp/venv/bin/python" \
     "/Users/aakashsrivastava/Documents/PolicyBazaar Claude/.claude/mcp/metabase-mcp/server.py"
```

Credentials are read from this project's `.env` file at runtime — nothing is passed via `-e` flags, so no credential ends up stored in Claude Code's own config file.

Named `metabase-own` to avoid colliding with the `metabase` connector already
installed from the third-party `@jerichosequitin/metabase-mcp` package.

## Safety

`run_sql` only accepts SELECT / WITH...SELECT statements — INSERT, UPDATE,
DELETE, DROP, ALTER, CREATE, TRUNCATE, GRANT, REVOKE, INTO, and stacked
statements are all rejected in code before any request reaches Metabase.
There is no env flag to disable this.

This is a keyword heuristic, not a full SQL sandbox. Two known limitations:
- A `SELECT` that calls a function or stored procedure which itself performs
  a write (e.g. `SELECT delete_all_policies()`, `SELECT lo_export(...)`) is
  not detectable by keyword matching and will pass through. The Metabase
  account used by this server should still hold read-only database
  permissions — this guard is defense-in-depth, not a substitute for that.
- A write keyword appearing inside a quoted string literal or SQL comment
  (e.g. `WHERE status = 'DELETE_REQUESTED'`) can cause a false rejection of
  an otherwise-safe query. This is an accepted trade-off of a text-based
  heuristic.

## License

MIT — see [LICENSE](LICENSE)

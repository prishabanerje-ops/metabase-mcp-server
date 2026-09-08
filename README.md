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

```bash
claude mcp add metabase-own --scope local \
  -e METABASE_URL=https://metabase.policybazaar.ae/ \
  -e METABASE_EMAIL='your.email@policybazaar.com' \
  -e METABASE_PASSWORD='your-password' \
  -- python3 "$(pwd)/server.py"
```

Named `metabase-own` to avoid colliding with the `metabase` connector already
installed from the third-party `@jerichosequitin/metabase-mcp` package.

## Safety

`run_sql` only accepts SELECT / WITH...SELECT statements — INSERT, UPDATE,
DELETE, DROP, ALTER, CREATE, TRUNCATE, GRANT, REVOKE, and stacked statements
are all rejected in code before any request reaches Metabase. There is no
env flag to disable this.

## License

MIT — see [LICENSE](LICENSE)

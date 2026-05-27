# AI Research Briefing MCP Server

This is a lightweight stdio MCP-compatible server for the MVP.

Example client command:

```powershell
python .\mcp-server\server.py
```

Tools:

- `generate_daily_digest`
- `read_daily_digest`
- `record_feedback`

For a production version, replace the stdlib JSON-RPC loop with the official MCP SDK and add authenticated source connectors.


# Oracle MCP (local Cursor only)

Optional Model Context Protocol server for managing Oracle Cloud Infrastructure from Cursor.

## Prerequisites (your local machine)

1. [OCI CLI](https://docs.oracle.com/en-us/iaas/Content/API/SDKDocs/cliinstall.htm) configured:
   ```bash
   oci setup config
   ```
2. [uv](https://docs.astral.sh/uv/) installed (`uvx` runs the MCP server)

## Enable in Cursor

This repo includes [`.cursor/mcp.json`](../../.cursor/mcp.json). Cursor → **Settings → MCP** → confirm `oracle-oci-api-mcp-server` is enabled.

Global alternative: copy the `mcpServers` block to `~/.cursor/mcp.json`.

## References

- [Oracle MCP quickstart](https://oracle-mcp.mintlify.app/quickstart)
- [oracle/mcp on GitHub](https://github.com/oracle/mcp)

MCP is optional — deployment uses SSH + scripts in this directory, not MCP.

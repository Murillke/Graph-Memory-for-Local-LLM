# MCP Server

Launch the memory MCP server with:

```bash
python3 mcp-server/memory_mcp.py
```

The server reads project and network settings from `mem.config.json` or `MEM_CONFIG`.

If your `mem.config.json` uses relative database paths like `./memory/...`, launch
the server with the repo root as the working directory. For MCP clients, the safe
pattern is:

```json
{
  "mcpServers": {
    "llm-memory": {
      "command": "python3.11",
      "args": [
        "/Users/davidastua/Documents/llm-mem/mcp-server/memory_mcp.py"
      ],
      "cwd": "/Users/davidastua/Documents/llm-mem",
      "env": {
        "MEM_CONFIG": "/Users/davidastua/Documents/llm-mem/mem.config.json"
      }
    }
  }
}
```

Without `cwd`, relative `sql_path` / `graph_path` values may resolve to the wrong
folder and appear as an empty project.

Key tools:

- `memory_recall`: time-window recall with optional entity relationship context
- `memory_search`: entity/fact/relationship search against the configured project
- `memory_context`: recent project snapshot for session bootstrapping
- `memory_store`: store a conversation exchange in SQL memory
- `memory_tasks`: list and mutate actionable tasks

HTTP transport is available with:

```bash
python3 mcp-server/memory_mcp.py --http
```

Requirements:

- `mcp[cli]>=1.26.0`
- `uvicorn>=0.24.0`
- `starlette>=0.35.0`

Private-network HTTP mode requires valid `mcp` settings in `mem.config.json`, including TLS when `network_mode` is `private`.

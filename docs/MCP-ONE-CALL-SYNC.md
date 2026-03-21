# MCP One-Call Sync Architecture

## Overview

The `memory_sync_submit` tool allows LLM agents to persist knowledge with a single call.
The agent provides an extended summary; the server handles extraction automatically.

## API

```python
memory_sync_submit(
    summary: str,           # Required: Extended summary of work
    session_id: str = None  # Optional: Auto-generated if not provided
)
```

### Summary Field

Provide a rich description including:
- Objectives and intent
- Approaches taken
- Work completed
- Results achieved
- Errors encountered and fixed
- Key decisions made
- Tools and technologies used

The richer the summary, the better the extraction.

## How It Works

1. **Idempotent Import**: Checks `get_unprocessed_interactions()` for existing session
2. **Import Summary**: Runs `import_summary.py` to store conversation in SQL
3. **LLM Extraction**: Uses Augment SDK `DirectContext.search_and_ask()` to extract entities/facts
4. **Retry on Failure**: If extraction fails, retries with error context (max 2 retries)
5. **Validate**: Runs `validate_extraction.py` to check schema
6. **Quality Review**: Runs `store_extraction.py` with auto-filled duplicate/contradiction answers
7. **Store**: Creates entities with proper `HAS_ENTITY` links to project

## Required Configuration

### MCP Server Environment Variables

Add to `~/.augment/settings.json`:

```json
{
  "mcpServers": {
    "llm-memory": {
      "command": "python3.11",
      "args": ["/path/to/mcp_server/memory_mcp.py"],
      "env": {
        "MEM_CONFIG": "/absolute/path/to/mem.config.json",
        "AUGMENT_API_TOKEN": "your-token-here",
        "AUGMENT_API_URL": "https://e9.api.augmentcode.com/"
      }
    }
  }
}
```

### Config File (mem.config.json)

**IMPORTANT**: Use absolute paths, not relative. MCP runs from different working directories.

```json
{
  "database": {
    "sql_path": "/absolute/path/to/memory/conversations.db",
    "graph_path": "/absolute/path/to/memory/project.graph"
  },
  "paths": {
    "tmp_dir": "/absolute/path/to/tmp",
    "memory_dir": "/absolute/path/to/memory"
  }
}
```

## Duplicate Handling

Entities with similarity ≥ 0.9 are automatically marked as duplicates and merged.
The `question_index` field is used to properly match quality questions with answers.

## LLM Retry Logic

On extraction failure:
1. First attempt with extraction prompt
2. If JSON parse or validation fails, retry with:
   - Original prompt
   - LLM's failed output  
   - Error message
3. Max 2 retries before failing

## Dependencies

- `auggie-sdk`: Install with `pip install auggie-sdk`
- Augment API token with valid subscription

## Troubleshooting

### Recall returns 0 entities
- Check `extraction_timestamp_str` on entities (should not be 1970-01-01)
- Verify `HAS_ENTITY` relationships exist
- Check config uses absolute paths

### MCP crashes on sync
- Verify `AUGMENT_API_TOKEN` is set in MCP env
- Check `auggie-sdk` is installed

### Duplicates being created
- Verify `question_index` matching in quality answers
- Check similarity threshold (default 0.9)


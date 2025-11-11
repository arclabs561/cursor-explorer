# Cognee MCP Issues Found and Fixes

## Issues Identified

1. **Database User Creation Error**: `UNIQUE constraint failed: users.email` when checking `cognify_status` or `codify_status` - happens when default user already exists
2. **Empty Status Responses**: `cognify_status` and `codify_status` return `{}` when no pipeline runs exist
3. **Empty Developer Rules**: `get_developer_rules` returns empty list `[]` instead of string when no rules exist, causing validation error
4. **Database Lock Errors**: Kuzu database lock errors when multiple processes try to access the database

## Fixes Applied (Local Patch)

A patch file has been created: `cognee-mcp-fixes.patch`

### To apply fixes after git pull:
```bash
cd /Users/arc/Documents/dev/devdev/cognee
git apply /Users/arc/Documents/dev/devdev/cognee-mcp-fixes.patch
```

### To revert fixes:
```bash
cd /Users/arc/Documents/dev/devdev/cognee
git restore cognee-mcp/src/server.py
```

## Proper Solution

These issues should be reported upstream to the cognee project:
- GitHub: https://github.com/topoteretes/cognee
- Issues: https://github.com/topoteretes/cognee/issues

## Current Workflow

1. **Normal usage**: Just use cognee-mcp as-is (with the known issues)
2. **With fixes**: Apply the patch after each `git pull`
3. **Upstream**: Report issues and contribute fixes upstream

## Notes

- The fixes improve error handling and user experience
- They don't change core functionality
- They should be safe to apply, but will be lost on `git pull`
- Consider forking the repo if you want to maintain these fixes long-term







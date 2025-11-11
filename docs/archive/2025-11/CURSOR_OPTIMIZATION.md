# Cursor-Specific Optimization for skill-mcp

## Understanding Cursor's MCP Integration

Based on your existing MCP configuration, here are Cursor-specific patterns and optimizations:

## Current Configuration Analysis

Your `~/.cursor/mcp.json` shows:
- ✅ **stdio transport** (default) - Used by most servers
- ✅ **Environment variables** - Used by firecrawl, magic, Snyk
- ✅ **Cursor-specific env vars** - `IDE_CONFIG_PATH` for Snyk

## Cursor-Specific Optimizations

### 1. Environment Variables for Cursor Context

Add Cursor-specific environment variables to help skill-mcp understand the context:

```json
{
  "mcpServers": {
    "skill-mcp": {
      "command": "uvx",
      "args": [
        "--from",
        "skill-mcp",
        "skill-mcp-server"
      ],
      "env": {
        "IDE_CONFIG_PATH": "Cursor",
        "SKILL_MCP_DIR": "~/.skill-mcp/skills"
      }
    }
  }
}
```

**Benefits:**
- `IDE_CONFIG_PATH`: Helps skill-mcp know it's running in Cursor
- `SKILL_MCP_DIR`: Explicit path (though it has a default)

### 2. Working Directory Context

For project-specific skills, you might want to set a working directory:

```json
{
  "mcpServers": {
    "skill-mcp": {
      "command": "uvx",
      "args": [
        "--from",
        "skill-mcp",
        "skill-mcp-server"
      ],
      "env": {
        "IDE_CONFIG_PATH": "Cursor",
        "CURSOR_WORKSPACE": "${workspaceFolder}"
      }
    }
  }
}
```

**Note:** Cursor may not support `${workspaceFolder}` - this is theoretical.

### 3. Performance Optimization

Cursor loads MCP servers on startup. Optimize for fast startup:

**Current (good):**
```json
{
  "command": "uvx",
  "args": ["--from", "skill-mcp", "skill-mcp-server"]
}
```

**Why this is optimal:**
- `uvx` caches packages, so subsequent starts are fast
- No local installation needed
- Always uses latest version

### 4. Error Handling for Cursor

Cursor may show MCP errors in its UI. To help debugging:

```json
{
  "mcpServers": {
    "skill-mcp": {
      "command": "uvx",
      "args": [
        "--from",
        "skill-mcp",
        "skill-mcp-server"
      ],
      "env": {
        "PYTHONUNBUFFERED": "1",
        "SKILL_MCP_LOG_LEVEL": "INFO"
      }
    }
  }
}
```

**Benefits:**
- `PYTHONUNBUFFERED`: Ensures logs appear immediately
- `SKILL_MCP_LOG_LEVEL`: Control logging verbosity

## Cursor-Specific Best Practices

### 1. Skill Naming for Cursor

Cursor shows skill names in its UI. Use clear, descriptive names:

- ✅ `git-workflow` - Clear and descriptive
- ❌ `gw` - Too cryptic
- ❌ `git_workflow_automation_tool` - Too long

### 2. Skill Descriptions

Cursor may show skill descriptions. Make them Cursor-friendly:

```markdown
---
name: git-workflow
description: Git operations for Cursor workflows - commit validation, rebase checks, branch management
---
```

**Key points:**
- Mention "Cursor" if Cursor-specific
- Keep descriptions concise (50-100 chars ideal)
- Focus on what it does, not how it works

### 3. Script Execution Context

When Cursor runs skill scripts, they execute in the context of:
- The workspace directory (if applicable)
- The user's environment
- Cursor's process environment

**Best practices:**
- Use absolute paths when needed
- Don't assume current working directory
- Handle environment variables gracefully

### 4. Tool Discovery in Cursor

Cursor discovers MCP tools on startup. To ensure tools are visible:

1. **Clear tool names**: Use descriptive, unique names
2. **Good descriptions**: Help Cursor understand what tools do
3. **Proper categories**: If skill-mcp supports categories, use them

## Debugging in Cursor

### Check MCP Server Status

Cursor may show MCP server status. Look for:
- Connection status indicators
- Error messages in Cursor's UI
- Log files in `~/Library/Application Support/Cursor/logs/`

### Enable Debug Logging

Add to your MCP config:

```json
{
  "mcpServers": {
    "skill-mcp": {
      "command": "uvx",
      "args": [
        "--from",
        "skill-mcp",
        "skill-mcp-server"
      ],
      "env": {
        "SKILL_MCP_LOG_LEVEL": "DEBUG",
        "PYTHONUNBUFFERED": "1"
      }
    }
  }
}
```

Then check Cursor logs:
```bash
tail -f ~/Library/Application\ Support/Cursor/logs/*/exthost/*/MCP*.log
```

### Test MCP Connection

In Cursor, ask Claude:
```
"What MCP tools do you have access to?"
```

Should list skill-mcp tools if connected.

## Performance Considerations

### Startup Time

Cursor loads MCP servers on startup. skill-mcp should be fast because:
- ✅ Uses `uvx` (cached packages)
- ✅ No heavy initialization
- ✅ Simple stdio transport

### Tool Discovery

Cursor discovers tools once on startup. To minimize impact:
- Keep tool lists reasonable (< 50 tools per server)
- Use clear, descriptive tool names
- Group related tools logically

### Script Execution

When Cursor executes skill scripts:
- Scripts run in separate processes
- Each execution is isolated
- Results are returned via MCP protocol

**Optimization tips:**
- Keep scripts fast (< 5 seconds ideally)
- Use timeouts for long-running operations
- Return structured data (JSON) when possible

## Cursor-Specific Features

### 1. Workspace Awareness

Cursor knows about your workspace. Skills can leverage this:

```python
# In a skill script
import os
workspace = os.getenv("CURSOR_WORKSPACE") or os.getcwd()
```

**Note:** Cursor may not set `CURSOR_WORKSPACE` - this is theoretical.

### 2. File System Access

Cursor's MCP servers have access to:
- User's home directory
- Workspace directory (if applicable)
- System paths

**Security:** Skills should validate paths to prevent directory traversal.

### 3. Environment Variables

Cursor passes environment variables to MCP servers. Your skills can use:
- `HOME` - User's home directory
- `PATH` - System PATH
- Custom env vars from MCP config

## Recommended Configuration

Here's an optimized configuration for Cursor:

```json
{
  "mcpServers": {
    "skill-mcp": {
      "command": "uvx",
      "args": [
        "--from",
        "skill-mcp",
        "skill-mcp-server"
      ],
      "env": {
        "IDE_CONFIG_PATH": "Cursor",
        "PYTHONUNBUFFERED": "1",
        "SKILL_MCP_LOG_LEVEL": "INFO"
      }
    }
  }
}
```

**Why these settings:**
- `IDE_CONFIG_PATH`: Identifies Cursor context
- `PYTHONUNBUFFERED`: Ensures immediate log output
- `SKILL_MCP_LOG_LEVEL`: Balanced logging (not too verbose)

## Testing in Cursor

### Quick Validation

After restarting Cursor, test with these prompts:

1. **"List all available skills"**
   - Should show git-workflow

2. **"What MCP tools can you use?"**
   - Should mention skill-mcp tools

3. **"Run branch_list.py from git-workflow skill"**
   - Should execute and return results

### Expected Behavior

When working correctly:
- ✅ Claude can discover skills
- ✅ Claude can read skill files
- ✅ Claude can execute skill scripts
- ✅ Results are returned correctly
- ✅ No errors in Cursor's UI

## Troubleshooting

### MCP Server Not Loading

1. **Check config syntax**:
   ```bash
   cat ~/.cursor/mcp.json | jq .
   ```

2. **Verify uvx**:
   ```bash
   which uvx
   uvx --version
   ```

3. **Test server manually**:
   ```bash
   uvx --from skill-mcp skill-mcp-server
   ```

### Tools Not Visible

1. **Restart Cursor** (MCP servers load on startup)
2. **Check Cursor logs** for errors
3. **Verify skill directory** exists and has SKILL.md

### Script Execution Fails

1. **Check script permissions**:
   ```bash
   ls -l ~/.skill-mcp/skills/git-workflow/scripts/*.py
   ```

2. **Test script directly**:
   ```bash
   python3 ~/.skill-mcp/skills/git-workflow/scripts/branch_list.py --help
   ```

3. **Check environment variables** in script

## Summary

**Current configuration is good!** The stdio transport with `uvx` is optimal for Cursor.

**Optional enhancements:**
- Add `IDE_CONFIG_PATH` for Cursor awareness
- Add `PYTHONUNBUFFERED` for better logging
- Set `SKILL_MCP_LOG_LEVEL` for debugging

**Key points:**
- Cursor loads MCP servers on startup (restart required)
- stdio transport is standard and works well
- Environment variables can help with debugging
- Clear skill names and descriptions help Cursor


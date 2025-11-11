# Cursor MCP Validation Guide

## The Reality Check

You're right to question this - **we can't fully validate MCP integration without actually testing it in Cursor**. Here's what we've validated and what you need to test:

## What We've Validated ✅

1. **File Structure**: All skill files exist and are correct
2. **Script Functionality**: Scripts work when run directly
3. **MCP Configuration**: Config file is correct
4. **MCP Tools (Direct)**: We can call the tools directly (but that's not the same as Cursor using them)

## What We CAN'T Validate Without Cursor ❌

1. **Cursor's MCP Server Connection**: Does Cursor actually connect to skill-mcp?
2. **Tool Availability in Cursor**: Can Claude see the skill-mcp tools?
3. **Skill Discovery**: Can Claude discover and use the skills?

## The Real Test: In Cursor

### Step 1: Restart Cursor
**This is critical** - MCP servers only load on startup.

```bash
# Quit Cursor completely
# Then reopen it
```

### Step 2: Ask Claude These Questions

Try these in Cursor's chat (in order of complexity):

#### Easy Tests:
1. **"What MCP tools do you have access to?"**
   - Should mention skill-mcp tools if connected

2. **"List all available skills"**
   - Should show git-workflow if working

#### Medium Tests:
3. **"Show me details about the git-workflow skill"**
   - Should return skill metadata

4. **"Read the SKILL.md file from git-workflow skill"**
   - Should show the file content

#### Hard Tests:
5. **"Run the branch_list.py script from git-workflow skill with --json flag"**
   - Should execute and return branch data

6. **"Execute merge_base.py from git-workflow to find merge base with origin/main in the cognee directory"**
   - Should return a commit hash

## What Success Looks Like

If Claude can:
- ✅ See and list the git-workflow skill
- ✅ Read skill files
- ✅ Execute skill scripts
- ✅ Return actual results from script execution

Then **everything is working!**

## What Failure Looks Like

If Claude:
- ❌ Says "I don't have access to skill-mcp tools"
- ❌ Can't find any skills
- ❌ Can't execute scripts
- ❌ Shows MCP connection errors

Then we need to troubleshoot.

## Troubleshooting Checklist

If it's not working:

1. **Verify config file**:
   ```bash
   cat ~/.cursor/mcp.json | jq '.mcpServers["skill-mcp"]'
   ```

2. **Check uvx**:
   ```bash
   which uvx
   uvx --version
   ```

3. **Test server manually**:
   ```bash
   uvx --from skill-mcp skill-mcp-server
   # Should start (will wait for input - Ctrl+C to exit)
   ```

4. **Check Cursor logs**:
   - Look for MCP errors in Cursor's log files
   - Usually in: `~/Library/Application Support/Cursor/logs/`

5. **Verify skill files**:
   ```bash
   ls -la ~/.skill-mcp/skills/git-workflow/
   ```

## The Bottom Line

**We've validated everything we can validate outside of Cursor.**

The final validation happens when you:
1. Restart Cursor
2. Ask Claude to use the skills
3. See if it works

If Claude can use the skills → **Success!** 🎉

If not → We troubleshoot based on the error messages.

## Quick Validation Script

After restarting Cursor, try this conversation:

```
You: "List all available skills"

Claude: [Should list git-workflow]

You: "Show me details about git-workflow"

Claude: [Should show skill details]

You: "Run branch_list.py from git-workflow with --json"

Claude: [Should execute and return branch data]
```

If all three work, **you're golden!** ✅


# How to Verify skill-mcp Works in Cursor

## The Real Test: Can Cursor See the Skills?

Since we're in Cursor, the actual validation happens when Cursor loads the MCP server. Here's how to verify it's working:

## Step 1: Restart Cursor

**Critical**: Cursor only loads MCP servers on startup. You must restart Cursor for the skill-mcp server to be available.

1. Quit Cursor completely (Cmd+Q on Mac)
2. Reopen Cursor
3. Wait a few seconds for MCP servers to initialize

## Step 2: Verify MCP Server is Loaded

### Option A: Check Cursor's MCP Status (if available)
- Look for MCP server status indicators in Cursor's UI
- Check for any error messages about MCP servers

### Option B: Ask Claude in Cursor
Try these prompts to verify the MCP server is working:

1. **"List all available MCP tools"**
   - Should show skill-mcp tools if the server is loaded

2. **"What skills do you have access to?"**
   - Should mention skill-mcp or git-workflow

3. **"Use the list_skills tool"**
   - Should list the git-workflow skill

## Step 3: Test skill-mcp Tools Directly

Ask Claude in Cursor to:

1. **"List available skills using the skill-mcp tools"**
   - Expected: Should show `git-workflow` skill

2. **"Show me details about the git-workflow skill"**
   - Expected: Should show skill metadata, scripts, etc.

3. **"Read the merge_base.py script from the git-workflow skill"**
   - Expected: Should show the script content

4. **"Run the branch_list script from git-workflow skill with --json flag"**
   - Expected: Should execute the script and return branch data

## Step 4: Verify Script Execution

If the MCP tools work, test actual script execution:

1. **"Execute the branch_list.py script from git-workflow skill in the cognee directory"**
   - Should return JSON with branch information

2. **"Run merge_base.py from git-workflow skill to find the merge base with origin/main"**
   - Should return a commit hash

## Troubleshooting

### If MCP tools don't appear:

1. **Check MCP config file**:
   ```bash
   cat ~/.cursor/mcp.json | jq '.mcpServers["skill-mcp"]'
   ```
   Should show:
   ```json
   {
     "command": "uvx",
     "args": ["--from", "skill-mcp", "skill-mcp-server"]
   }
   ```

2. **Verify uvx is available**:
   ```bash
   which uvx
   uvx --version
   ```

3. **Test MCP server manually**:
   ```bash
   uvx --from skill-mcp skill-mcp-server
   ```
   Should start the server (you'll see it waiting for input)

4. **Check Cursor logs**:
   - Look for MCP-related errors in Cursor's logs
   - On Mac: `~/Library/Application Support/Cursor/logs/`

### If skills aren't found:

1. **Verify skill directory**:
   ```bash
   ls -la ~/.skill-mcp/skills/
   ls -la ~/.skill-mcp/skills/git-workflow/
   ```

2. **Check SKILL.md exists**:
   ```bash
   cat ~/.skill-mcp/skills/git-workflow/SKILL.md | head -10
   ```

3. **Verify scripts are executable**:
   ```bash
   ls -l ~/.skill-mcp/skills/git-workflow/scripts/*.py
   ```

## Expected Behavior in Cursor

When working correctly, you should be able to:

✅ Ask Claude to list skills and see `git-workflow`
✅ Ask Claude to show skill details and get full metadata
✅ Ask Claude to read skill files and see the content
✅ Ask Claude to run skill scripts and get results

## The Real Validation

**The only real validation is: Can you use the skills in Cursor?**

If you can ask Claude to:
- List skills → ✅ Working
- Get skill details → ✅ Working  
- Read skill files → ✅ Working
- Run skill scripts → ✅ Working

Then everything is validated and working!

## Quick Test Commands

Run these in Cursor's chat to verify:

```
"List all available skills"
"Show me the git-workflow skill details"
"Read the SKILL.md file from git-workflow"
"Run branch_list.py from git-workflow with --json flag"
```

If Claude can do these, **it's working!** 🎉


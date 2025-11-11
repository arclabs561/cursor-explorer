# Cursor MCP Integration Checklist

## Pre-Flight Checks ✅

- [x] MCP config file exists: `~/.cursor/mcp.json`
- [x] skill-mcp configured in MCP config
- [x] `uvx` is available in PATH
- [x] Skills directory exists: `~/.skill-mcp/skills/`
- [x] git-workflow skill created and has SKILL.md
- [x] All scripts are executable
- [x] MCP server can start (tested manually)

## Cursor-Specific Configuration ✅

- [x] Using stdio transport (default, optimal for Cursor)
- [x] Using `uvx` for package management (fast, cached)
- [x] Added Cursor-specific environment variables:
  - `IDE_CONFIG_PATH`: "Cursor"
  - `PYTHONUNBUFFERED`: "1" (for immediate logs)
  - `SKILL_MCP_LOG_LEVEL`: "INFO" (balanced logging)

## Post-Restart Validation

After restarting Cursor, verify:

### 1. MCP Server Connection
- [ ] Ask Claude: "What MCP tools do you have access to?"
- [ ] Should mention skill-mcp tools
- [ ] No errors in Cursor's UI

### 2. Skill Discovery
- [ ] Ask Claude: "List all available skills"
- [ ] Should show `git-workflow`
- [ ] Should show skill description

### 3. Skill Details
- [ ] Ask Claude: "Show me details about git-workflow skill"
- [ ] Should return skill metadata
- [ ] Should list all scripts

### 4. File Reading
- [ ] Ask Claude: "Read the SKILL.md file from git-workflow"
- [ ] Should show file content
- [ ] Should be formatted correctly

### 5. Script Execution
- [ ] Ask Claude: "Run branch_list.py from git-workflow with --json flag"
- [ ] Should execute script
- [ ] Should return branch data (if in git repo)
- [ ] Should handle errors gracefully

## Troubleshooting

If something doesn't work:

### MCP Server Not Loading
1. Check Cursor logs: `~/Library/Application Support/Cursor/logs/`
2. Verify config: `cat ~/.cursor/mcp.json | jq .`
3. Test server: `uvx --from skill-mcp skill-mcp-server`

### Skills Not Found
1. Verify directory: `ls -la ~/.skill-mcp/skills/git-workflow/`
2. Check SKILL.md: `cat ~/.skill-mcp/skills/git-workflow/SKILL.md | head -10`
3. Verify scripts: `ls -l ~/.skill-mcp/skills/git-workflow/scripts/`

### Script Execution Fails
1. Test directly: `python3 ~/.skill-mcp/skills/git-workflow/scripts/branch_list.py --help`
2. Check permissions: `ls -l ~/.skill-mcp/skills/git-workflow/scripts/*.py`
3. Check Python: `python3 --version`

## Success Criteria

✅ All 5 validation steps pass
✅ Claude can discover and use skills
✅ Scripts execute and return results
✅ No errors in Cursor's UI
✅ Skills work as expected

## Next Steps After Validation

Once validated:
1. Use skills in your workflows
2. Create additional skills as needed
3. Share skills with team (if applicable)
4. Document any custom configurations


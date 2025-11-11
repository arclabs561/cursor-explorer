# Skill-MCP Usage Rules for AI Assistant

## Quick Reference

### When to Use skill-mcp Tools

| User Request | Tool to Use | Why |
|-------------|-------------|-----|
| "What skills do we have?" | `list_skills` | Direct skill discovery |
| "Show me git-workflow details" | `get_skill_details` | Skill information |
| "Run branch_list script" | `run_skill_script` | Executing skill script |
| "Show me merge_base.py code" | `read_skill_file` | Reading skill files |
| "Validate commits in my branch" | `run_skill_script` | Composed workflow |
| "What's my current branch?" | `run_terminal_cmd("git branch")` | Simple operation |
| "Add a file to git-workflow" | skill-mcp CRUD tools | Skill management |

### Decision Tree

```
User Request
    │
    ├─ About skills? 
    │   └─ Use: list_skills, get_skill_details
    │
    ├─ Run skill script?
    │   └─ Use: run_skill_script
    │   └─ BUT: Only if it's a workflow, not simple command
    │
    ├─ Simple git command?
    │   └─ Use: run_terminal_cmd (NOT skill-mcp)
    │
    └─ Complex workflow?
        └─ Use: run_skill_script (if skill exists)
```

## Rules

### Rule 1: Skills are for Composition
- ✅ Use skills for workflows that compose multiple operations
- ❌ Don't use skills for single, simple commands

### Rule 2: Always Validate
- ✅ Check skill exists with `list_skills` before use
- ✅ Verify script path with `get_skill_details`
- ❌ Don't assume skills/scripts exist

### Rule 3: Use Right Tool for Job
- ✅ Simple operations → `run_terminal_cmd`
- ✅ Skill workflows → `run_skill_script`
- ✅ File operations → `read_file`/`write_file`

### Rule 4: Error Handling
- ✅ Always handle errors gracefully
- ✅ Provide helpful error messages
- ✅ Suggest alternatives when tools fail

## Examples

### ✅ Correct Usage

**User:** "List all available skills"
```python
skills = list_skills()
# Returns: List of skills
```

**User:** "Run branch_list from git-workflow to see my branches"
```python
result = run_skill_script(
    "git-workflow",
    "scripts/branch_list.py",
    args=["--json"]
)
# Returns: Branch data in JSON
```

**User:** "Validate all commits in my branch"
```python
result = run_skill_script(
    "git-workflow",
    "scripts/rebase_check.py",
    args=["--start", "origin/main"]
)
# This is a composed workflow - correct use
```

### ❌ Incorrect Usage

**User:** "What's my current git branch?"
```python
# WRONG:
run_skill_script("git-workflow", "scripts/branch_list.py")

# RIGHT:
run_terminal_cmd("git rev-parse --abbrev-ref HEAD")
```

**User:** "Add a file to the repo"
```python
# WRONG:
# Using skill-mcp tools for simple git add

# RIGHT:
run_terminal_cmd("git add filename")
```

## Validation Checklist

Before using skill-mcp tools, verify:

- [ ] Is this about skills themselves? → Use skill-mcp tools
- [ ] Is this a simple operation? → Use direct tools
- [ ] Does the skill exist? → Check with `list_skills`
- [ ] Does the script exist? → Check with `get_skill_details`
- [ ] Will this benefit from composition? → Use skill-mcp
- [ ] Are parameters correct? → Validate before calling

## Remember

**Skills = Workflow Composition**
**Direct Tools = Simple Operations**

Use the right tool for the job!


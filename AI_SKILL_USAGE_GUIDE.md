# AI Assistant Guide: Using skill-mcp Tools Correctly

## The Core Question

**How do I (the AI assistant) know when and how to use skill-mcp tools correctly?**

## My Tool Discovery Process

1. **I see tools in my available tool list** - skill-mcp tools appear alongside other MCP tools
2. **I read tool descriptions** - Each tool has a description explaining what it does
3. **I check skill documentation** - Skills have SKILL.md files with usage guidelines
4. **I follow patterns** - I learn from examples and user feedback

## Decision Framework for Me

### When I Should Use skill-mcp Tools

#### ✅ Use `list_skills` when:
- User asks "what skills do we have?"
- User asks "list available skills"
- I need to check if a skill exists before using it
- User wants to see what's available

#### ✅ Use `get_skill_details` when:
- User asks about a specific skill
- I need to understand what a skill does
- I need to see what scripts/files a skill has
- User asks "show me details about git-workflow"

#### ✅ Use `read_skill_file` when:
- User wants to see skill code
- User asks "show me the merge_base script"
- I need to understand how a skill works
- User wants to review skill implementation

#### ✅ Use `run_skill_script` when:
- User explicitly asks to run a skill script
- User wants a workflow that composes skill operations
- The operation benefits from skill's error handling/validation
- It's part of a larger composed workflow

#### ✅ Use `read_skill_env` / `update_skill_env` when:
- User asks about skill environment variables
- User wants to configure a skill
- Managing skill configuration

### When I Should NOT Use skill-mcp Tools

#### ❌ Don't use for simple operations:
- `git status` → Use `run_terminal_cmd("git status")`
- `git add .` → Use `run_terminal_cmd("git add .")`
- `ls` → Use `list_dir` or `run_terminal_cmd("ls")`
- Reading a file → Use `read_file` directly

#### ❌ Don't use when direct tools are better:
- Simple file operations → Use `read_file`, `write_file`
- Simple commands → Use `run_terminal_cmd`
- Code search → Use `grep`, `codebase_search`

## My Decision Process

### Step 1: Understand the Request
- What is the user actually asking for?
- Is it about skills themselves?
- Is it a simple operation?
- Is it a complex workflow?

### Step 2: Check Available Tools
- Do I have a skill-mcp tool that fits?
- Would a direct tool be simpler?
- Does this benefit from skill composition?

### Step 3: Validate Before Use
- Does the skill exist? (use `list_skills` first)
- Does the script exist? (check `get_skill_details`)
- Are the parameters correct?

### Step 4: Execute and Handle Errors
- Run the tool with correct parameters
- Handle errors gracefully
- Provide helpful feedback

## Examples of Correct Usage

### Example 1: User asks "What skills do we have?"
```python
# ✅ CORRECT: Use list_skills
skills = list_skills()
# Return: List of skills with descriptions
```

### Example 2: User asks "Run branch_list from git-workflow"
```python
# ✅ CORRECT: Use run_skill_script
result = run_skill_script(
    skill_name="git-workflow",
    script_path="scripts/branch_list.py",
    args=["--json"]
)
# Return: Branch data
```

### Example 3: User asks "What's my current git branch?"
```python
# ✅ CORRECT: Use run_terminal_cmd (simple operation)
result = run_terminal_cmd("git rev-parse --abbrev-ref HEAD")
# NOT: run_skill_script("git-workflow", "scripts/branch_list.py")
```

### Example 4: User asks "Validate commits in my branch"
```python
# ✅ CORRECT: Use skill (composable workflow)
result = run_skill_script(
    "git-workflow",
    "scripts/rebase_check.py",
    args=["--start", "origin/main"]
)
# This is a complex workflow that benefits from skill's error handling
```

## Anti-Patterns I Should Avoid

### ❌ Anti-Pattern 1: Over-using skills
```python
# WRONG: Using skill for simple git command
run_skill_script("git-workflow", "scripts/branch_list.py")  # Just to get current branch

# RIGHT: Use direct command
run_terminal_cmd("git rev-parse --abbrev-ref HEAD")
```

### ❌ Anti-Pattern 2: Not checking skill existence
```python
# WRONG: Assuming skill exists
run_skill_script("nonexistent-skill", "script.py")

# RIGHT: Check first
skills = list_skills()
if "git-workflow" in [s.name for s in skills]:
    run_skill_script("git-workflow", "script.py")
```

### ❌ Anti-Pattern 3: Using skills for one-off operations
```python
# WRONG: Creating/using skill for single command
run_skill_script("git-workflow", "scripts/merge_base.py", ["origin/main"])

# RIGHT: If it's truly one-off, use direct command
run_terminal_cmd("git merge-base HEAD origin/main")
```

## Self-Validation Checklist

Before using skill-mcp tools, I should ask:

1. ✅ **Is this about skills?** → Use skill-mcp tools
2. ✅ **Is this a simple operation?** → Use direct tools instead
3. ✅ **Does this benefit from composition?** → Consider skill-mcp
4. ✅ **Does the skill exist?** → Check with `list_skills` first
5. ✅ **Are parameters correct?** → Validate before calling
6. ✅ **Will this help the user?** → Use the right tool for the job

## Key Principles for Me

1. **Skills are for composition, not simple operations**
2. **Always validate skill existence before use**
3. **Use direct tools when simpler**
4. **Compose skills for complex workflows**
5. **Handle errors gracefully**
6. **Provide clear feedback**

## How I Learn

1. **Tool descriptions** - I read what each tool does
2. **Skill documentation** - SKILL.md files explain usage
3. **User feedback** - When I use tools incorrectly, user corrects me
4. **Patterns** - I learn from examples and successful usage
5. **Guidelines** - Documents like this help me understand

## Testing My Understanding

To verify I understand correctly, I should:

1. **List skills when asked** - Use `list_skills` for skill discovery
2. **Use skills for workflows** - Use `run_skill_script` for composed operations
3. **Use direct tools for simple ops** - Use `run_terminal_cmd` for simple commands
4. **Validate before use** - Check skill existence and parameters
5. **Handle errors** - Provide helpful error messages

## Summary

**I should use skill-mcp tools when:**
- User asks about skills
- User wants to run skill scripts
- Operations benefit from skill composition
- Complex workflows that need orchestration

**I should NOT use skill-mcp tools when:**
- Simple operations (use direct tools)
- One-off commands (use `run_terminal_cmd`)
- Operations that don't benefit from abstraction

**Always:**
- Validate skill existence first
- Use the right tool for the job
- Handle errors gracefully
- Provide clear feedback


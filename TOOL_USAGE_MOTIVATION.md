# Tool Usage Motivation: The Real Solution

## The Problem You Identified

**Just having skill-mcp tools available doesn't mean I'll use them.** What actually motivates me to choose skill-mcp tools over direct commands?

## The Answer: Explicit Prompts + Self-Advertising Skills

### What I Need to Use Tools Correctly

1. **Explicit User Request → Tool Call Mappings**
   - "When user says 'validate commits' → use run_skill_script(...)"
   - Not just "this tool exists"

2. **Clear Benefits**
   - "Returns structured JSON vs plain text"
   - "Handles errors gracefully"
   - Makes the choice obvious

3. **Decision Rules**
   - "Use skill when: structured output needed"
   - "Use direct when: simple operation"

4. **Examples**
   - Concrete "user says X → do Y" patterns
   - Before/after comparisons

## What I've Implemented

### 1. Updated SKILL.md with "🤖 For AI Assistants" Section

The skill now includes explicit guidance:

```markdown
## 🤖 For AI Assistants: Explicit Usage Guide

### User Requests → Tool Calls

When the user makes these requests, **use `run_skill_script` from skill-mcp**:

#### 1. "Validate commits" / "Check if commits pass"
**User says:**
- "Validate my commits"
- "Check if my commits pass lint"

**You should:**
```python
run_skill_script(
    skill_name="git-workflow",
    script_path="scripts/rebase_check.py",
    args=["--start", "origin/main"]
)
```

**Why:** Returns structured JSON, handles errors, provides actionable feedback.
```

This makes it **obvious** when to use the skill.

### 2. Created .cursorrules

Project-level rules that guide behavior:

```markdown
## Skill-MCP Tool Usage

When the user requests git operations, check if a skill exists first:

1. **User asks to validate commits** → Use `run_skill_script("git-workflow", "scripts/rebase_check.py")`
2. **User asks to list branches** → Use `run_skill_script("git-workflow", "scripts/branch_list.py", ["--json"])`
...
```

### 3. Decision Framework

Clear rules for when to use what:

- **Use skill when:** Structured output, error handling, composable workflows
- **Use direct when:** Simple one-off operations

## How This Actually Works

### Before (No Motivation)
```
User: "Validate my commits"
Me: [Sees many tools, defaults to simplest]
    → Uses run_terminal_cmd("git log") ❌
```

### After (With Explicit Prompts)
```
User: "Validate my commits"
Me: [Reads SKILL.md, sees explicit mapping]
    → "When user says 'validate commits' → use run_skill_script(...)"
    → Uses run_skill_script("git-workflow", "scripts/rebase_check.py") ✅
```

## The Key Insight

**Skills must be self-advertising with explicit AI prompts.**

Not just:
- "This skill does X" (descriptive)

But:
- "When user says Y → use this tool Z" (action-oriented)
- "Why: returns structured JSON vs plain text" (clear benefit)
- "Example: user says 'validate commits' → use run_skill_script(...)" (concrete)

## What Makes This Work

1. **Explicit Mappings** - User request → tool call (no ambiguity)
2. **Clear Benefits** - Why skill is better (structured output, error handling)
3. **Decision Rules** - When to use what (structured vs simple)
4. **Examples** - Concrete patterns (user says X → do Y)
5. **Project Rules** - .cursorrules guides behavior

## Testing

To verify this works, test with:

1. **"Validate my commits"**
   - Should: Use `run_skill_script("git-workflow", "scripts/rebase_check.py")`
   - Not: Use `run_terminal_cmd("git log")`

2. **"List my branches"**
   - Should: Use `run_skill_script("git-workflow", "scripts/branch_list.py", ["--json"])`
   - Not: Use `run_terminal_cmd("git branch")`

3. **"What's my current branch?"**
   - Should: Use `run_terminal_cmd("git rev-parse --abbrev-ref HEAD")`
   - Not: Use skill (too simple)

## The Bottom Line

**Motivation comes from explicit, action-oriented prompts that:**
1. Map user requests to tool calls
2. Explain why skills are better
3. Provide decision rules
4. Include concrete examples

**Without these, I'll default to direct commands because they're simpler and more obvious.**

The solution: **Make skills self-advertising with explicit AI assistant guidance.**


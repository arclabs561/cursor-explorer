# The Real Question: What Motivates Tool Usage?

## The Problem

Just because skill-mcp tools are **available** doesn't mean I'll **use** them. What actually drives tool selection?

## How Tool Selection Works

### What I See
- Tool list with descriptions
- Tool parameters and schemas
- Context about what's available

### What I Don't Automatically Know
- **When** to prefer skill-mcp tools over direct tools
- **Why** skills are better for certain operations
- **How** to discover skills exist in the first place

## The Motivation Gap

### Current State
1. Tools are available ✅
2. Tools have descriptions ✅
3. But: No clear signal to USE them ❌

### What's Missing
- **Explicit prompts** that guide usage
- **Examples** in skill documentation
- **Context** that makes skills the obvious choice
- **User requests** that naturally lead to skills

## Solutions: Making Skills the Obvious Choice

### 1. Skill Self-Documentation

Skills should advertise themselves:

```markdown
# Git Workflow Skill

## 🤖 AI Assistant: Use This Skill When...

- User asks to "validate commits" → Use `run_skill_script` with `rebase_check.py`
- User asks to "list branches" → Consider if workflow, else use direct git
- User asks to "find merge base" → Use `run_skill_script` with `merge_base.py`
```

### 2. Explicit Usage Prompts in Skills

Add to SKILL.md:

```markdown
## For AI Assistants

When user requests:
- "Validate my commits" → Use `run_skill_script("git-workflow", "scripts/rebase_check.py")`
- "List my branches" → Use `run_skill_script("git-workflow", "scripts/branch_list.py", ["--json"])`
- "Find merge base" → Use `run_skill_script("git-workflow", "scripts/merge_base.py", ["origin/main"])`

Why use this skill instead of direct commands:
- Provides structured error handling
- Returns JSON for further processing
- Handles edge cases automatically
```

### 3. Tool Descriptions That Guide Usage

Tool descriptions should be action-oriented:

```python
# Current (descriptive):
"List all available skills"

# Better (action-oriented):
"List all available skills. Use this when user asks 'what skills do we have?' or before using any skill to verify it exists."
```

### 4. Context-Aware Prompts

Skills should include prompts that make them discoverable:

```markdown
## Common User Requests That Trigger This Skill

- "Validate commits in my branch"
- "Check if my commits pass lint"
- "List branches sorted by date"
- "Find where my branch diverged"
- "Create a fixup commit"
```

### 5. Skill Discovery Mechanism

When user asks about git operations, I should:
1. Check if a skill exists for this operation
2. Compare skill vs direct tool
3. Choose the better option

But this requires:
- **Explicit guidance** in skill docs
- **Clear examples** of when to use
- **Comparison** with direct alternatives

## The Real Solution: Skill Prompts

Skills need to include **explicit prompts for AI assistants**:

```markdown
## AI Assistant Usage Guide

### When User Says:
- "Validate my commits" → Use `run_skill_script("git-workflow", "scripts/rebase_check.py")`
- "List branches" → Use `run_skill_script("git-workflow", "scripts/branch_list.py", ["--json"])`
- "Find merge base" → Use `run_skill_script("git-workflow", "scripts/merge_base.py", ["origin/main"])`

### Why Use This Skill:
- Returns structured JSON (better for processing)
- Handles errors gracefully
- Provides validation and checks
- Composable with other operations

### When NOT to Use:
- Simple `git status` → Use `run_terminal_cmd` directly
- One-off `git add` → Use `run_terminal_cmd` directly
```

## Implementation Strategy

### 1. Update SKILL.md with AI Prompts

Add a section specifically for AI assistants with:
- Common user requests
- Exact tool calls to make
- Why use skill vs direct tool
- Examples

### 2. Make Tool Descriptions Action-Oriented

Update tool descriptions to include:
- When to use
- What user requests trigger it
- Why it's better than alternatives

### 3. Create Skill Usage Patterns

Document common patterns:
- "User asks X → Use skill Y"
- "User wants workflow Z → Compose skills A + B"

### 4. Add to .cursorrules

Include in project .cursorrules:
- When to check for skills
- When to prefer skills over direct tools
- How to discover and use skills

## The Bottom Line

**Tools being available ≠ Tools being used**

I need:
1. **Explicit prompts** in skill documentation
2. **Clear examples** of when to use
3. **Comparison** with alternatives
4. **Action-oriented** tool descriptions
5. **Context** that makes skills the obvious choice

Without these, I'll default to direct tools because they're simpler and more obvious.


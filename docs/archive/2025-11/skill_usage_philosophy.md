# Skill Usage Philosophy: When and Where to Use Skills

## The Core Question

**When should you create a skill vs. using tools directly vs. making them available to Cursor?**

## Answer: Skills for Composition, Not Just Exposure

Skills should be created when they provide **composable, reusable functionality** that enhances workflows, not just to expose every tool to Cursor.

## Decision Framework

### ✅ Create a Skill When:

1. **Composable Operations**: Can be combined with other operations in workflows
2. **Non-Interactive Automation**: Needs to run without human input (CI/CD, scripts)
3. **Complex Multi-Step Workflows**: Orchestrates multiple commands with state management
4. **Integration Points**: Provides clean API over complex operations or integrates with other tools
5. **Frequently Repeated Patterns**: You find yourself doing the same sequence repeatedly

### ❌ Don't Create a Skill When:

1. **Simple One-Off Operations**: Single commands like `git add`, `ls`, `cat`
2. **Interactive Workflows**: Require human judgment at each step
3. **Unstable Patterns**: Still being explored, haven't stabilized
4. **Over-Abstraction**: Wrapping simple operations unnecessarily

## Real Examples from This Codebase

### ✅ Good: `git-workflow` Skill

**Why it's good:**
- Composes multiple git operations (rebase_check, commit_fixup, merge_base)
- Provides non-interactive automation for commit management
- Integrates with linting/testing workflows
- Reusable across projects
- Handles error cases and validation

**Usage:**
```python
# Composable workflow
result = rebase_check(base_commit="abc123")
if not result["success"]:
    for commit in result["failed_commits"]:
        commit_fixup(commit)
```

### ❌ Bad: `git-add` Skill

**Why it's bad:**
- Single, simple operation
- Already well-served by `git add` directly
- No composition or workflow benefit
- Unnecessary abstraction

**Better:** Use `git add` directly or include in larger workflow skill

## Cognee Integration: Lessons Learned

### Known Issues with Cognee MCP

From `cognee-mcp-issues.md`:
1. Database user creation errors (UNIQUE constraint failures)
2. Empty status responses
3. Empty developer rules causing validation errors
4. Database lock errors with multiple processes

### Should Cognee Be a Skill?

**Current State**: Cognee is already an MCP server, not a skill.

**Consideration**: Should we create a `cognee-integration` skill?

**Answer**: **Maybe, but with caution**

**Create a skill if:**
- You frequently compose cognee operations with other workflows
- You need non-interactive automation of cognee operations
- You want to abstract away the known issues with better error handling
- You're building workflows that combine cognee with other tools

**Don't create a skill if:**
- You're just wrapping the existing MCP tools
- The patterns aren't stable yet
- You're still exploring cognee functionality
- Direct MCP tool access is sufficient

### Recommended Approach for Cognee

1. **Use MCP tools directly** for now (they're already available)
2. **Monitor usage patterns** - do you find yourself repeating cognee operations?
3. **Create a skill later** if patterns emerge that benefit from composition
4. **Address known issues** in the cognee MCP server itself (upstream fixes)

## Integration with Cursor

### When to Expose Skills to Cursor:

1. **Workflow Enhancement**: Enhances development workflows beyond direct access
2. **Composition Benefits**: Can be composed with other MCP tools
3. **Error Handling**: Provides better validation and error messages

### When NOT to Expose:

1. **Simple Operations**: Direct tool access is sufficient
2. **Exploratory Work**: Patterns haven't stabilized
3. **Over-Abstraction**: Adding complexity without clear benefit

## Skill Architecture

### Three Tiers:

1. **Library Skills** (Reusable Components)
   - `git-utils`: Basic git operations
   - `file-utils`: File operations
   - `db-utils`: Database operations

2. **Workflow Skills** (Composed Operations)
   - `git-workflow`: Composes git-utils for workflows
   - `code-quality`: Composes linting, testing, formatting
   - `cursor-chat-analysis`: Composes search, indexing, vector operations

3. **Application Skills** (Domain-Specific)
   - `cognee-integration`: Domain-specific cognee workflows (if patterns emerge)
   - `project-setup`: Project-specific setup workflows

## Anti-Patterns to Avoid

1. **Skill Sprawl**: Creating skills for every operation
2. **Premature Abstraction**: Creating skills before patterns stabilize
3. **Over-Engineering**: Adding complexity without clear benefit
4. **Tool Proliferation**: Exposing too many tools to Cursor
5. **Ignoring Direct Access**: Not using direct tool access when appropriate

## Summary

**The key insight**: Skills are for **composition and workflow enhancement**, not just tool exposure.

**Create skills when they:**
- Provide composable, reusable functionality
- Enhance workflows beyond direct tool access
- Integrate with other tools/skills
- Handle complex multi-step operations
- Benefit from structured error handling

**Don't create skills when:**
- Simple direct tool access is sufficient
- Operations are one-off or exploratory
- Patterns haven't stabilized
- Over-abstraction adds no value

**For Cognee specifically:**
- Use existing MCP tools directly for now
- Monitor for repeated patterns
- Create a skill later if composition patterns emerge
- Focus on fixing known issues upstream


# Repo Cleanup & Organization Plan

## Current State Analysis

This repo mixes multiple concerns:
1. **cursor_explorer** - Python tool for analyzing Cursor chats
2. **dotfiles/** - Personal dotfiles management
3. **bin/** - Scripts (duplicate of dotfiles/home/bin?)
4. **cognee/** - Large Python knowledge graph project
5. **Generated data files** - *.json, *.jsonl, *.db, *.sqlite in root
6. **Validation docs** - Multiple analysis/validation markdown files

## Issues to Address

### 1. Unnecessary Files to Prune

**Generated/Data Files (should be gitignored or moved):**
- `*.jsonl` files (cursor_index.jsonl, daily_chat_index.jsonl, etc.) - generated data
- `*.db`, `*.sqlite` files - databases (already in .gitignore)
- `*.json` data files (streams_*.json, findings_*.json, etc.) - generated analysis
- `logs/` directory - log files
- `test_log.log` - test output

**Documentation Sprawl:**
- `CURSOR_OPTIMIZATION.md`
- `CURSOR_VALIDATION.md`
- `VALIDATION_COMPLETE.md`
- `VALIDATION_RESULTS.md`
- `cursor_mcp_checklist.md`
- `verify_cursor_mcp.md`
- `skill_analysis.md`
- `skill_usage_philosophy.md`
- `cognee-mcp-*.md` files

These should be:
- Consolidated into `docs/` directory
- Or archived to `docs/archive/YYYY-MM-DD/`
- Or removed if obsolete

### 2. Directory Structure

**bin/ vs dotfiles/home/bin/**
- `bin/` doesn't exist in repo root (only in dotfiles/home/bin/)
- This is correct - scripts are in dotfiles/home/bin/ and get symlinked to ~/bin

### 3. Organization Issues

**Separate Concerns:**
- `cursor_explorer/` is the main tool (Python)
- `dotfiles/` is personal config (bash script) - could be separate repo
- Mixing tool development with personal dotfiles creates confusion

## Recommended Structure

### Option A: Keep Together (Monorepo Style)
```
devdev/
├── cursor_explorer/     # Main tool
│   ├── src/
│   ├── tests/
│   └── README.md
├── dotfiles/            # Dotfiles (or symlink to ~/dev/dotfiles)
├── scripts/             # Shared scripts
├── docs/                # All documentation
│   ├── archive/         # Old validation/analysis docs
│   └── ...
├── data/                # Generated data (gitignored)
└── README.md
```

### Option B: Split Repos (Recommended)
1. **devdev** - cursor_explorer tool only
2. **dotfiles** - separate repo (or use ~/dev/dotfiles)
3. **cognee** - separate submodule or remove if not needed

## Modern Dotfiles Manager Options

### Recommendation: KEEP BASH SCRIPT

**Research Conclusion**: For an 82-line symlink script, Bash is the right choice.

**Why Bash Wins:**
- ✅ Zero dependencies (bash is universal on Unix)
- ✅ Copy-paste ready (no compilation needed)
- ✅ Easy to understand and modify
- ✅ Already works perfectly
- ✅ Performance is identical for I/O operations

**Why NOT Rust:**
- ❌ Requires Rust compiler or pre-built binaries
- ❌ Adds friction for users (dependency burden)
- ❌ Overkill for simple symlink operations
- ❌ Existing tools (Dotter, Rotz, Chezmoi) already solve complex cases

**If You Need More Features:**
- Use existing Rust tools (Dotter, Rotz, Chezmoi) rather than building your own
- Only convert if you need complex templating, state management, or Windows native support

### Current Setup Assessment
- Your 82-line bash script is **perfectly appropriate** for the task
- It's simple, works, and has zero dependencies
- Focus on **documentation** and **organization** rather than rewriting

## Action Items

### Immediate Cleanup (High Priority)

1. **Move generated data files to `data/` directory**
   ```bash
   mkdir -p data
   mv *.jsonl *.json data/ 2>/dev/null || true
   # Update .gitignore to ignore data/
   ```

2. **Archive old validation docs**
   ```bash
   mkdir -p docs/archive/2025-11
   mv CURSOR_*.md VALIDATION_*.md cursor_mcp_*.md verify_*.md skill_*.md docs/archive/2025-11/
   ```

3. **Update .gitignore**
   - Add `data/` directory
   - Ensure `*.db`, `*.sqlite` are ignored (already done)
   - Add `logs/` if not already there

4. **Clean up root directory**
   - Move `test_log.log` to `logs/` or delete
   - Organize remaining files

### Organization (Medium Priority)

**Recommended: Split Repos**
1. **devdev** - Keep only cursor_explorer tool
   - `src/`, `tests/`, `scripts/`, `docs/`
   - Remove `dotfiles/` (move to separate repo or ~/dev/dotfiles)

2. **dotfiles** - Separate repo (or use ~/dev/dotfiles)
   - Keep bash script (it's perfect as-is)
   - Add better README with examples
   - Make it shareable with clear documentation

### Dotfiles Modernization (Low Priority - Not Recommended)

**Decision: Keep Bash Script**
- Your script is appropriate for the task
- Focus on documentation, not rewriting
- If you need more features later, evaluate existing tools (Dotter, Rotz)

## Questions Resolved

1. ✅ `cognee/` - Doesn't exist, no action needed
2. ✅ `bin/` - Only exists in dotfiles/home/bin/ (correct structure)
3. ❓ Should dotfiles be separate? - **RECOMMENDED: Yes, separate repo**
4. ❓ Make shareable? - **Keep bash, add documentation**

## Recommended Final Structure

### Option A: Split (Recommended)
```
devdev/                    # cursor_explorer only
├── src/
├── tests/
├── scripts/
├── docs/
├── data/                  # gitignored
└── README.md

~/dev/dotfiles/            # Separate repo
├── home/
├── misc/
├── setup
└── README.md
```

### Option B: Keep Together (Monorepo)
```
devdev/
├── cursor_explorer/
│   ├── src/
│   └── tests/
├── dotfiles/              # Personal config
├── docs/
│   └── archive/
├── data/                  # gitignored
└── README.md
```


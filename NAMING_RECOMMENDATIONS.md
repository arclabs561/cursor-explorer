# Directory Naming & Structure Recommendations

## Current State

### Repository Name
- **Current**: `devdev`
- **Project Name** (pyproject.toml): `cursor-chat-explorer` ✓
- **Issue**: Repo name doesn't match project purpose

### Directory Structure
```
devdev/
├── bin/              # Scripts (OK)
├── cognee/           # Git submodule (OK)
├── cognee-data/      # ⚠️ Confusing - cognee-specific data
├── data/             # ⚠️ Confusing - conflicts with cognee-data
├── docs/             # Documentation (OK)
├── dotfiles/         # Personal config (OK)
├── logs/             # Logs (OK)
├── prompts/          # Prompts (OK)
├── scripts/          # Build scripts (OK)
├── seeds/            # Seed data (OK)
├── src/              # Python source (OK)
└── tests/            # Tests (OK)
```

## Issues Identified

### 1. Naming Conflicts
- **`cognee-data/` vs `data/`**: Both are data directories, confusing
- **Solution**: Rename `cognee-data/` to `cognee-cache/` or `cognee-storage/`

### 2. Repository Name
- **Current**: `devdev` (unclear)
- **Should be**: `cursor-explorer` or `cursor-chat-explorer` (matches project name)

### 3. Directory Clarity
- `data/` - Generic name, but OK for cursor_explorer data
- `cognee-data/` - Should be more specific

## Recommendations

### Option A: Rename cognee-data (Recommended)
```bash
# Rename cognee-data to cognee-storage (more descriptive)
mv cognee-data cognee-storage
```

**Pros**:
- More descriptive name
- Clearer purpose (storage for cognee)
- No conflict with `data/`

**Cons**:
- Need to update any references in code/docs
- Need to update .gitignore

### Option B: Consolidate Data Directories
```bash
# Move cognee-data into data/cognee/
mkdir -p data/cognee
mv cognee-data/* data/cognee/
rmdir cognee-data
```

**Pros**:
- Single data directory
- Better organization

**Cons**:
- More complex migration
- May break cognee if it expects specific path

### Option C: Keep As-Is
- Document the difference clearly
- Add README in each directory explaining purpose

## Recommended Actions

1. **Rename `cognee-data/` → `cognee-storage/`**
   - More descriptive
   - Clearer purpose
   - Update .gitignore

2. **Repository Name** (if creating new repo)
   - Use `cursor-explorer` or `cursor-chat-explorer`
   - Matches project name in pyproject.toml

3. **Documentation**
   - Add README in `data/` explaining it's for cursor_explorer
   - Add README in `cognee-storage/` explaining it's for cognee

## GitHub Auth Status

✅ **Already Configured**:
- Account: `arclabs561` (active)
- Account: `henrywallace` (inactive)
- Token scopes: `gist`, `read:org`, `repo`, `user`, `workflow`, `write:packages`

**Note**: If you need private repo access, it's already configured. The `repo` scope includes private repositories.

## Implementation

See `RENAME_PLAN.md` for step-by-step instructions.


# Repository Rename Plan

## Current Situation

### Repository Name
- **Local directory**: `devdev`
- **Project name** (pyproject.toml): `cursor-chat-explorer`
- **GitHub**: Not yet created (not a git repo)

### GitHub Username
- **Previous**: `henrywallace` (referenced in dotfiles remote)
- **Current**: Need to verify (you mentioned renaming)
- **Also seen**: `arclabs561` (active account)

## Recommended New Name

**Option 1**: `cursor-explorer` (shorter, cleaner)
- Matches common naming conventions
- Easy to type and remember
- Available on GitHub (likely)

**Option 2**: `cursor-chat-explorer` (matches pyproject.toml)
- Exactly matches project name
- More descriptive
- Consistent with package name

**Recommendation**: `cursor-explorer` (Option 1)

## Rename Steps

### 1. Rename Local Directory

```bash
# From parent directory
cd /Users/arc/Documents/dev
mv devdev cursor-explorer
cd cursor-explorer
```

### 2. Update Internal References

**Files that may reference "devdev":**
- `.gitignore` - Check for any devdev-specific paths
- `README.md` - Update if it mentions repo name
- `pyproject.toml` - Already correct (`cursor-chat-explorer`)
- Documentation files - Review and update

### 3. Create GitHub Repository

```bash
# Initialize git (if not already)
git init

# Add all files
git add .

# Initial commit
git commit -m "Initial commit: cursor-explorer v0.1.0"

# Create GitHub repo with new name
gh repo create cursor-explorer --public --source=. --remote=origin

# Push
git push -u origin main
```

### 4. Update Dotfiles Remote ✅ DONE

**Status**: Updated from `henrywallace` to `arclabs561`

```bash
# Already completed:
cd dotfiles
git remote set-url origin git@github.com:arclabs561/dotfiles
```

**Note**: The public repo `arclabs561/dotfiles` contains personal information and needs to be sanitized (see `URGENT_DOTFILES_FIX.md`).

## Files to Review/Update

### Before Renaming
- [ ] Check `.gitignore` for any devdev-specific paths
- [ ] Review `README.md` for repo name references
- [ ] Check documentation files
- [ ] Verify `pyproject.toml` project name (already correct)

### After Renaming
- [ ] Update any hardcoded paths in documentation
- [ ] Verify all references are updated
- [ ] Test that everything still works

## Dotfiles Remote Update

### Current Status
- Local `./dotfiles/` points to: `git@github.com:henrywallace/dotfiles`
- Public repo exists: `github.com/arclabs561/dotfiles`

### Action Needed
1. **Determine current username**:
   ```bash
   gh api user --jq '.login'
   ```

2. **Update dotfiles remote**:
   ```bash
   cd dotfiles
   git remote set-url origin git@github.com:CURRENT_USERNAME/dotfiles
   ```

3. **Verify remote exists**:
   ```bash
   gh repo view CURRENT_USERNAME/dotfiles
   ```

## Recommended Structure After Rename

```
/Users/arc/Documents/dev/
├── cursor-explorer/          # Main repo (renamed from devdev)
│   ├── src/
│   ├── tests/
│   ├── scripts/
│   ├── docs/
│   ├── data/                 # gitignored
│   ├── logs/                 # gitignored
│   ├── cognee-storage/       # gitignored
│   └── README.md
│
└── dotfiles/                 # Separate (or ~/dev/dotfiles)
    ├── home/
    ├── misc/
    └── setup
```

## Pre-Rename Checklist

- [ ] Verify current GitHub username
- [ ] Check if `cursor-explorer` name is available
- [ ] Review all files for "devdev" references
- [ ] Backup current state (just in case)
- [ ] Update dotfiles remote if username changed
- [ ] Decide on final name: `cursor-explorer` vs `cursor-chat-explorer`

## Post-Rename Checklist

- [ ] Verify directory renamed successfully
- [ ] Test that all scripts still work
- [ ] Create GitHub repo with new name
- [ ] Push initial commit
- [ ] Update any bookmarks/links
- [ ] Verify dotfiles remote is correct


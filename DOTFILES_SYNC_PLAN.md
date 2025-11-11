# Dotfiles Repository Sync Plan

## Current Situation

### Remote Repositories
1. **github.com/arclabs561/dotfiles** (PUBLIC)
   - Status: Exists, is public
   - Default branch: `master`
   - ⚠️ **PUBLIC REPO** - personal info should not be here

2. **github.com/henrywallace/dotfiles** (unknown)
   - Status: Local `./dotfiles/` points to this remote
   - Need to verify if this repo exists

### Local Setup
- `./dotfiles/` in this repo is a git repository
  - Points to: `git@github.com:henrywallace/dotfiles`
  - Contains personal info (`.gitconfig` with email, name, paths)
- `~/dev/dotfiles` may exist (needs verification)
  - If exists, likely the primary dotfiles location
  - `./dotfiles/` in cursor_explorer repo may be redundant

## ⚠️ Critical Issue

**The public repo `arclabs561/dotfiles` should NOT contain personal information!**

If it currently does, you need to:
1. Sanitize the public repo immediately
2. Remove personal info from all files
3. Use templates (`.example` files) instead

## Action Plan

### Option A: Keep Public Repo Sanitized (Recommended)

1. **Sanitize public repo** (`arclabs561/dotfiles`):
   ```bash
   # Clone the public repo
   gh repo clone arclabs561/dotfiles ~/temp-dotfiles-public
   cd ~/temp-dotfiles-public
   
   # Remove personal info
   # - Replace .gitconfig with .gitconfig.example
   # - Remove hardcoded paths
   # - Remove personal domains/emails
   
   # Commit and push
   git add .
   git commit -m "Sanitize: Remove personal information"
   git push
   ```

2. **Keep private version separate**:
   - Use `henrywallace/dotfiles` as private repo (or make it private)
   - Or keep local only (no remote)
   - Contains full personal configuration

3. **Update local setup**:
   ```bash
   # Option 1: Point to public repo (sanitized)
   cd dotfiles
   git remote set-url origin git@github.com:arclabs561/dotfiles
   
   # Option 2: Keep pointing to private repo
   # (current setup - verify henrywallace/dotfiles exists/is private)
   ```

### Option B: Make arclabs561/dotfiles Private

1. **Change repo visibility**:
   ```bash
   gh repo edit arclabs561/dotfiles --visibility private
   ```

2. **Then personal info is OK**:
   - Can sync local with remote
   - Personal info acceptable in private repo

### Option C: Separate Public Template Repo

1. **Keep public repo as template**:
   - `arclabs561/dotfiles` = public template (sanitized)
   - `henrywallace/dotfiles` = private personal config

2. **Structure**:
   ```
   arclabs561/dotfiles (public template)
   ├── home/
   │   ├── .gitconfig.example
   │   └── ... (all sanitized)
   
   henrywallace/dotfiles (private personal)
   ├── home/
   │   ├── .gitconfig (with personal info)
   │   └── ... (full config)
   ```

## Immediate Actions Required

### 1. Verify Public Repo Contents
```bash
# Check what's actually in the public repo
gh repo view arclabs561/dotfiles --json files
gh api repos/arclabs561/dotfiles/contents/home/.gitconfig
```

### 2. If Personal Info Exists in Public Repo
- ⚠️ **URGENT**: Remove immediately
- Sanitize all files
- Use `.example` templates
- Consider making repo private if you want to keep personal info

### 3. Decide on Local Setup
- Keep `./dotfiles/` in this repo? (not recommended)
- Remove from cursor_explorer repo? (recommended)
- Use `~/dev/dotfiles` and link to remote?

## Recommendations

1. **For cursor_explorer repo**:
   - Remove `dotfiles/` directory (it's a separate concern)
   - Add `dotfiles/` to `.gitignore` if keeping locally
   - Focus repo on cursor_explorer only

2. **For dotfiles**:
   - If public: Must be sanitized (no personal info)
   - If private: Personal info OK
   - Keep separate from cursor_explorer repo

3. **Sync Strategy**:
   - Public repo = sanitized template
   - Private/local = full personal config
   - Use `setup` script to link from either location

## Next Steps

1. ✅ Verify what's in `arclabs561/dotfiles` public repo
2. ⚠️ If personal info exists: Sanitize immediately
3. 🔧 Decide: Public template vs Private personal
4. 📦 Remove `dotfiles/` from cursor_explorer repo
5. 🔗 Set up proper sync between local and remote


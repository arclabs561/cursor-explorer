# Git History Cleanup Guide

## Current Status

**Not a git repository yet** - This is actually good! You can start fresh with a clean history.

## Options for Clean History

### Option A: Fresh Start (Recommended)

Since you're not a git repo yet, you can initialize with a clean history:

```bash
# Initialize git repo
git init

# Add all files (respecting .gitignore)
git add .

# Create initial commit
git commit -m "Initial commit: cursor-explorer v0.1.0"

# If you want to publish to GitHub
gh repo create cursor-explorer --public --source=. --remote=origin
git push -u origin main
```

**Pros**:
- Clean history from the start
- No sensitive data in history
- Professional appearance

**Cons**:
- Lose any existing history (but you don't have any yet)

### Option B: If You Have Existing History Elsewhere

If you have this code in another repo with messy history:

```bash
# Clone the messy repo
git clone <messy-repo-url> temp-repo
cd temp-repo

# Create orphan branch (no history)
git checkout --orphan clean-main

# Add all files
git add .

# Create clean initial commit
git commit -m "Initial commit: cursor-explorer v0.1.0"

# Remove old branches
git branch -D main 2>/dev/null || true
git branch -m main

# Force push to new clean repo
git remote set-url origin <new-clean-repo-url>
git push -u origin main --force
```

### Option C: BFG Repo Cleaner (If History Exists)

If you need to clean existing history:

```bash
# Install BFG
brew install bfg  # or download from https://rtyley.github.io/bfg-repo-cleaner/

# Clone a fresh copy
git clone --mirror <repo-url> repo.git

# Remove sensitive files from history
bfg --delete-files .env
bfg --delete-files "*.key"
bfg --delete-files "*.secret"

# Remove sensitive text patterns
bfg --replace-text passwords.txt  # File with old=new mappings

# Clean up
cd repo.git
git reflog expire --expire=now --all
git gc --prune=now --aggressive

# Push cleaned history
git push --force
```

## Recommended Approach for Your Situation

Since you're **not a git repo yet**, use **Option A: Fresh Start**

### Step-by-Step

1. **Review files before committing**:
   ```bash
   # Check what will be committed
   git status
   git diff --cached
   ```

2. **Ensure .gitignore is comprehensive**:
   ```bash
   # Verify sensitive files are ignored
   cat .gitignore
   # Should include: .env, data/, logs/, cognee-storage/, etc.
   ```

3. **Initialize and commit**:
   ```bash
   git init
   git add .
   git commit -m "Initial commit: cursor-explorer v0.1.0"
   ```

4. **Create GitHub repo** (if publishing):
   ```bash
   gh repo create cursor-explorer --public --source=. --remote=origin
   git push -u origin main
   ```

## For Dotfiles (Separate Private Repo)

Since dotfiles contain personal info, keep them in a **private repo**:

```bash
# In dotfiles directory
cd dotfiles
git init
git add .
git commit -m "Initial commit: personal dotfiles"

# Create private repo
gh repo create dotfiles --private --source=. --remote=origin
git push -u origin main
```

## Pre-Commit Checklist

Before your first commit:

- [ ] `.gitignore` includes all sensitive files
- [ ] No `.env` files in repo
- [ ] No API keys in code
- [ ] No personal info in public files
- [ ] `dotfiles/` excluded (or in separate private repo)
- [ ] `data/`, `logs/`, `cognee-storage/` ignored
- [ ] All paths use variables, not hardcoded

## Post-Commit Security

After publishing:

1. **Verify nothing leaked**:
   ```bash
   # Check what's actually in the repo
   git ls-files
   
   # Search for potential secrets
   git grep -i "api.*key\|secret\|password\|token" -- ':!*.md'
   ```

2. **Set up secret scanning** (GitHub):
   - Enable GitHub Advanced Security (if available)
   - Use GitHub Secret Scanning
   - Consider tools like `git-secrets` or `truffleHog`

3. **Monitor for leaks**:
   - Set up alerts for exposed secrets
   - Regularly audit what's public


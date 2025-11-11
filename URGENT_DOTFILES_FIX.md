# 🔴 URGENT: Public Repo Contains Personal Information

## Critical Issue

**The public repository `github.com/arclabs561/dotfiles` contains personal information that is currently exposed.**

### What's Exposed
- Personal email: `henry@henrywallace.io`
- Personal name: `Henry Wallace`
- GitHub username: `henrywallace`
- Absolute paths: `/Users/arc/Documents/dev/devdev/dotfiles/misc/git-hooks`

### Impact
- Personal information is publicly accessible
- Anyone can see your email and name
- Potential for spam/phishing
- Privacy violation

## Immediate Fix Options

### Option 1: Sanitize Public Repo (Recommended)

```bash
# Clone the public repo
gh repo clone arclabs561/dotfiles ~/temp-dotfiles-fix
cd ~/temp-dotfiles-fix

# Replace .gitconfig with template
cp home/.gitconfig home/.gitconfig.example
# Edit .gitconfig.example to remove personal info
# Or use the template we created: dotfiles/home/.gitconfig.example

# Remove personal info from other files
# - Fix hardcoded paths in systemd files
# - Remove personal domain from bin/gp
# - Fix paths in bin/rmount

# Commit and push
git add .
git commit -m "Security: Remove personal information from public repo"
git push origin master
```

### Option 2: Make Repo Private (Quick Fix)

```bash
# Make the repo private immediately
gh repo edit arclabs561/dotfiles --visibility private
```

**Then later**: Sanitize and make public again, or keep private.

### Option 3: Delete Public Repo (If Not Needed)

```bash
# Only if you don't need a public dotfiles repo
gh repo delete arclabs561/dotfiles --yes
```

## Files That Need Sanitization

1. **home/.gitconfig**
   - Replace with `.gitconfig.example` template
   - Remove: email, name, absolute paths

2. **misc/systemd/user/up.service.d/override.conf**
   - Replace `/home/henrywallace/` with `$HOME/`

3. **misc/systemd/user/up.service**
   - Replace `/home/henrywallace/` with `$HOME/`

4. **bin/gp**
   - Replace `henrywallace.io` with placeholder

5. **bin/rmount**
   - Replace `/home/henrywallace/mnt/` with `$HOME/mnt/`

## Quick Sanitization Script

```bash
#!/bin/bash
# Run this in the public repo directory

# Replace .gitconfig
mv home/.gitconfig home/.gitconfig.example
sed -i '' 's/henry@henrywallace.io/your.email@example.com/g' home/.gitconfig.example
sed -i '' 's/Henry Wallace/Your Name/g' home/.gitconfig.example
sed -i '' 's/henrywallace/yourusername/g' home/.gitconfig.example
sed -i '' 's|/Users/arc/Documents/dev/devdev|~|g' home/.gitconfig.example

# Fix systemd files
find misc/systemd -type f -exec sed -i '' 's|/home/henrywallace|$HOME|g' {} \;

# Fix bin scripts
sed -i '' 's|henrywallace.io|example.com|g' bin/gp
sed -i '' 's|/home/henrywallace/mnt/|$HOME/mnt/|g' bin/rmount

echo "Sanitization complete. Review changes before committing."
```

## After Fixing

1. **Verify**:
   ```bash
   # Check what's public now
   gh repo view arclabs561/dotfiles
   # Search for personal info
   gh api repos/arclabs561/dotfiles/contents/home/.gitconfig
   ```

2. **Monitor**:
   - Set up alerts for exposed secrets
   - Regularly audit public repos

3. **Prevent Future Issues**:
   - Use `.example` templates for sensitive files
   - Review before pushing to public repos
   - Consider using pre-commit hooks to check for secrets

## Current Status

- ✅ Template created: `dotfiles/home/.gitconfig.example`
- ⚠️ Public repo needs immediate sanitization
- 📋 See `DOTFILES_SYNC_PLAN.md` for long-term strategy


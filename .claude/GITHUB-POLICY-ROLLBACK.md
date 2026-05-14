# GitHub Policy: Rollback & Recovery Guide

**Policy Version**: 1.0  
**Last Updated**: 2026-05-14  
**Status**: ACTIVE

---

## Overview

This document explains how to disable or recover from the GitHub Policy if needed. The policy is enforced via a **git pre-push hook** that can be safely disabled or removed without affecting your repository history.

---

## Quick Rollback

### Option 1: Disable Hook (Temporary)

If you need to push without running the policy checks:

```bash
# Push without the pre-push hook
git push origin <branch> --no-verify
```

⚠️ **Warning**: This bypasses ALL safety checks. Only use if:
- You've manually verified the commit is safe
- You're in an emergency situation
- The policy is genuinely broken

### Option 2: Remove Hook (Permanent)

To permanently disable the policy:

```bash
# Remove the pre-push hook
rm .git/hooks/pre-push

# Verify it's gone
ls .git/hooks/pre-push 2>&1
# Expected: "No such file or directory"
```

### Option 3: Restore Hook

To re-enable the policy after disabling it:

```bash
# Reinstall the hook
bash .claude/scripts/install-pre-push-hook.sh
```

---

## Troubleshooting

### Problem: Hook is blocking legitimate commits

**Symptom**: You get a policy check failure on a commit you know is safe

**Solution 1**: Fix the specific issue
```bash
# Review the error message from pre-push-check.sh
# Fix the staged files according to the error
# Retry the push
git push origin <branch>
```

**Solution 2**: Temporarily bypass (if truly urgent)
```bash
git push origin <branch> --no-verify
```

**Solution 3**: Adjust the policy
Edit `.claude/scripts/pre-push-check.sh` to adjust thresholds or patterns, then retry.

---

### Problem: Hook fails with "script not found"

**Symptom**: Error like `pre-push-check.sh: No such file or directory`

**Solution**:
```bash
# Reinstall the hook (it may have lost its path reference)
bash .claude/scripts/install-pre-push-hook.sh
```

---

### Problem: Hook interferes with automated tools (CI/CD, etc.)

**Symptom**: GitHub Actions, automated deployments, or other tools can't push

**Solution**: Use `--no-verify` in CI/CD pipelines:
```yaml
# GitHub Actions example
- name: Push changes
  run: git push origin main --no-verify
```

The hook only runs locally — it doesn't exist in CI environments.

---

## Complete Removal

To completely remove the GitHub Policy and all its files:

```bash
# 1. Remove the pre-push hook
rm .git/hooks/pre-push

# 2. Remove policy documentation
rm .claude/GITHUB-POLICY.md
rm .claude/GITHUB-POLICY-SETUP.md
rm .claude/GITHUB-POLICY-ROLLBACK.md

# 3. Remove scripts
rm .claude/scripts/pre-push-check.sh
rm .claude/scripts/install-pre-push-hook.sh

# 4. Commit the removal
git add -A
git commit -m "chore: remove GitHub Policy"
git push origin main
```

---

## Recovery from Accidental Policy Removal

If the policy files were deleted by accident:

### Quick Recovery (from backup)

```bash
# Check if git has the previous version
git log --all --oneline | grep -i "github-policy"

# Restore from a recent commit
git checkout <commit-hash> -- .claude/GITHUB-POLICY.md
git checkout <commit-hash> -- .claude/scripts/pre-push-check.sh
```

### Full Recovery (restore everything)

```bash
# List all deleted policy files
git log --diff-filter=D --summary | grep "GitHub Policy"

# Restore each file from the commit before deletion
git checkout <commit-before-deletion>~1 -- .claude/GITHUB-POLICY.md
git checkout <commit-before-deletion>~1 -- .claude/GITHUB-POLICY-SETUP.md
git checkout <commit-before-deletion>~1 -- .claude/GITHUB-POLICY-ROLLBACK.md
git checkout <commit-before-deletion>~1 -- .claude/scripts/pre-push-check.sh
git checkout <commit-before-deletion>~1 -- .claude/scripts/install-pre-push-hook.sh

# Reinstall the hook
bash .claude/scripts/install-pre-push-hook.sh

# Commit the recovery
git add -A
git commit -m "chore: recover GitHub Policy files"
```

---

## Rollback Impact Analysis

| Component | Impact | Recovery Time |
|-----------|--------|-----------------|
| .git/hooks/pre-push | Removes policy checks | Immediate (reinstall with script) |
| .claude/scripts/ | Removes check logic | Immediate (restore from git) |
| .claude/GITHUB-POLICY.md | Removes documentation | Immediate (restore from git) |
| Git history | **No impact** | N/A (history unchanged) |
| Existing commits | **No impact** | N/A (all commits preserved) |
| GitHub repository | **No impact** | N/A (no changes sent to GitHub) |

**Important**: Disabling or removing the policy does NOT affect:
- Any commits already pushed to GitHub
- Any work in progress
- The git repository structure
- Repository history

---

## Policy Modification (Without Full Rollback)

If you want to adjust the policy rather than remove it:

### Adjust Check Patterns

Edit `.claude/scripts/pre-push-check.sh` and modify:

```bash
# Line 49-56: API key patterns
patterns=(
    "sk_[a-zA-Z0-9]"  # Add, remove, or modify patterns
)

# Line 117-124: Required .gitignore entries
required_ignores=(
    ".env"  # Add or remove patterns
)

# Line 17: File size threshold
MAX_FILE_SIZE=$((100 * 1024 * 1024))  # Adjust as needed
```

### Adjust Check Severity

Modify the `print_check` function calls in each check to change PASS/FAIL behavior:

```bash
# Example: make .gitignore check a warning instead of failure
if [ $missing -eq 0 ]; then
    print_check ".gitignore coverage" "PASS"  # Change to WARN if desired
else
    print_check ".gitignore coverage" "WARN"  # Change severity
fi
```

### Test Modified Policy

```bash
# After modifying the script, test it:
bash .claude/scripts/pre-push-check.sh origin main

# Should see updated behavior
```

---

## Policy Upgrade Path

If a new version of the GitHub Policy is released:

### Step 1: Backup Current Config

```bash
cp .claude/scripts/pre-push-check.sh .claude/scripts/pre-push-check.sh.backup
```

### Step 2: Update Files

Download or git pull the new policy files:
```bash
git pull origin main
# or manually download new versions
```

### Step 3: Merge Custom Patterns (if any)

If you modified the script, manually merge your changes:
```bash
# Compare backup with new version
diff .claude/scripts/pre-push-check.sh.backup .claude/scripts/pre-push-check.sh

# Apply any custom patterns from backup to new version
```

### Step 4: Reinstall Hook

```bash
bash .claude/scripts/install-pre-push-hook.sh
```

### Step 5: Test New Policy

```bash
bash .claude/scripts/pre-push-check.sh origin main
```

---

## Emergency Procedures

### If Policy is Completely Broken

```bash
# 1. Bypass to get work done (temporary)
git push origin <branch> --no-verify

# 2. Diagnose the issue
bash .claude/scripts/pre-push-check.sh origin main 2>&1 | head -50

# 3. Option A: Remove and restore
rm .git/hooks/pre-push
bash .claude/scripts/install-pre-push-hook.sh

# 4. Option B: Restore from git
git checkout HEAD -- .claude/scripts/pre-push-check.sh
bash .claude/scripts/install-pre-push-hook.sh
```

### If You Cannot Access the Scripts

```bash
# Manually recreate the pre-push hook
mkdir -p .git/hooks

cat > .git/hooks/pre-push << 'EOF'
#!/bin/bash
REPO_ROOT="$(git rev-parse --show-toplevel)"
bash "$REPO_ROOT/.claude/scripts/pre-push-check.sh" "$@"
exit $?
EOF

chmod +x .git/hooks/pre-push
```

---

## Verifying Policy State

### Check if Policy is Active

```bash
ls -la .git/hooks/pre-push
# If it exists and is executable (-rwxr-xr-x), policy is ACTIVE
# If "No such file or directory", policy is DISABLED
```

### Check Policy Files Exist

```bash
ls -la .claude/GITHUB-POLICY.md
ls -la .claude/scripts/pre-push-check.sh
# If both exist, policy is installed
```

### Test Policy Functionality

```bash
# Create a test commit
echo "test" > .claude/.test.txt
git add .claude/.test.txt

# Try to push (should trigger hook)
git push origin HEAD 2>&1 | head -20
# Should see "GitHub Policy: Pre-Push Security Check" message

# Clean up
git reset HEAD .claude/.test.txt
rm .claude/.test.txt
```

---

## Support & Escalation

| Issue | Action |
|-------|--------|
| Policy blocks safe commit | Review error, fix issue, retry push |
| Policy is broken | Reinstall hook with `install-pre-push-hook.sh` |
| Need emergency bypass | Use `git push --no-verify` |
| Want to disable policy | Run `rm .git/hooks/pre-push` |
| Want to re-enable policy | Run `bash .claude/scripts/install-pre-push-hook.sh` |
| Want to modify policy | Edit `.claude/scripts/pre-push-check.sh` |

---

## Checklist: Before Removing Policy

Before you remove the policy, ensure:

- [ ] You understand why the policy needs to be removed
- [ ] You've backed up any custom configurations
- [ ] You've reviewed the policy impact analysis above
- [ ] You have a plan to re-enable it if needed
- [ ] You've documented the reason for removal

---

## Post-Rollback Steps

After removing or disabling the policy:

1. **Document why** — Update Engram or your local notes with the reason
2. **Consider alternatives** — Was there a way to fix the policy instead?
3. **Plan re-enablement** — When/how will the policy be restored?
4. **Notify team** — If this is a shared repository, inform other contributors
5. **Audit history** — Review what was pushed without policy protection

---

## Version History

| Version | Date | Status | Notes |
|---------|------|--------|-------|
| 1.0 | 2026-05-14 | ACTIVE | Initial release with 5 core checks |


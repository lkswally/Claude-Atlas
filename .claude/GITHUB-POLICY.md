# GitHub Policy: Operational Procedures for Secure Pushes

**Status**: ✅ Active  
**Effective Date**: 2026-05-14  
**Policy Version**: 1.0  
**Last Updated**: 2026-05-14

---

## Philosophy

This GitHub Policy establishes operational guardrails to ensure that **only safe, verified, and non-sensitive changes** are pushed to [github.com/lkswally/Claude-Atlas](https://github.com/lkswally/Claude-Atlas) (main branch). The policy is **preventive** (blocks risky pushes before they reach GitHub) rather than reactive (cleanup after exposure).

The policy balances:
- **Security**: Zero secrets, tokens, API keys, or credentials in any commit
- **Quality**: No large binaries, cache files, or unintended files
- **Stability**: Only commits with clear, meaningful messages
- **Trust**: Auditability and rollback capability for every protected push

---

## Scope

This policy applies to:

✅ **Applies to**:
- All pushes to `origin/main` branch
- All pushes to feature branches that will be merged to main
- Manual git operations from the CLI in D:\ProyectosIA\ProyectosClaude

❌ **Does NOT apply to**:
- Local git operations in other repositories or machines
- GitHub web UI operations (pull requests, direct edits, releases)
- Branches outside the Claude-Atlas repository
- Development branches not intended for main merge

---

## Core Safety Checks

The policy is enforced via pre-push hooks that execute **5 mandatory security checks**. All checks must PASS before a push is allowed to proceed.

### Check 1: API Keys & Tokens Detection

**Purpose**: Prevent accidental exposure of authentication credentials

**Patterns Detected**:
- Stripe keys: `sk_[a-zA-Z0-9]`
- Groq API: `gsk_[a-zA-Z0-9]`
- Resend API: `re_[a-zA-Z0-9]`
- Telegram-like tokens: `AAH[a-zA-Z0-9]`
- Private keys: `-----BEGIN.*PRIVATE.*KEY`
- Certificates: `-----BEGIN CERTIFICATE`

**Failure Mode**: If ANY staged file contains these patterns, the check FAILS and push is blocked.

**Remediation**:
```bash
# Remove the secret from the file, then:
git reset HEAD <file>
git checkout -- <file>
# OR edit the file to remove the secret, then:
git add <file>
git commit --amend --no-edit
```

---

### Check 2: Hardcoded Credentials Detection

**Purpose**: Prevent hardcoded passwords, API keys, or secrets in environment-like variables

**Patterns Detected**:
- `password.*=` assignments
- `api.?key.*=` assignments (api_key, apikey, api-key)
- `secret.*=` assignments
- Excludes function declarations like `password()` in code

**Failure Mode**: If ANY staged file contains credential assignments, the check WARNS (status=FAIL) and push is blocked.

**Remediation**:
```bash
# Replace hardcoded values with environment variable references:
# BEFORE: const apiKey = "sk_live_12345"
# AFTER: const apiKey = process.env.API_KEY || ""

# Then commit the fix:
git add <file>
git commit -m "fix: use environment variables for credentials"
```

---

### Check 3: .gitignore Coverage

**Purpose**: Verify that sensitive file types and cache directories are properly excluded

**Required Ignores** (must be present in .gitignore):
- `.env` — environment variable files
- `.secret` — secret directories
- `*.key` — private key files
- `*.pem` — certificate/key files
- `__pycache__` — Python cache
- `node_modules` — JavaScript dependencies
- `*.db` — database files

**Failure Mode**: If ANY required pattern is missing from .gitignore, the check FAILS and push is blocked.

**Remediation**:
```bash
# Add missing patterns to .gitignore
echo ".env" >> .gitignore
echo "*.key" >> .gitignore
# ... add others as needed
git add .gitignore
git commit -m "fix: ensure .gitignore has required patterns"
```

---

### Check 4: Large Files Detection

**Purpose**: Prevent large binaries, compiled code, or media from bloating the repository

**Threshold**: 100MB (configurable in pre-push-check.sh)

**Failure Mode**: If ANY staged file exceeds 100MB, the check FAILS and push is blocked.

**Remediation**:
```bash
# Option A: Remove the large file
git reset HEAD <large-file>
rm <large-file>
git add .gitignore  # make sure it's in .gitignore
git commit --amend --no-edit

# Option B: Use Git LFS (if file is needed)
git lfs track "<large-file>"
git add .gitattributes
git add <large-file>
git commit --amend --no-edit
```

---

### Check 5: Cache & Temp Files Detection

**Purpose**: Exclude auto-generated and cache files that should never be committed

**Patterns Detected**:
- `__pycache__` — Python cache
- `.pytest_cache` — Pytest cache
- `node_modules` — Node.js dependencies
- `.next/cache` — Next.js build cache
- `*.pyc` — Python bytecode
- `*.tmp` — Temporary files
- `.DS_Store` — macOS system file

**Failure Mode**: If ANY staged file matches these patterns, the check FAILS and push is blocked.

**Remediation**:
```bash
# Remove the cache files from git tracking
git reset HEAD <cache-file-or-dir>
# Ensure they're in .gitignore
git status  # verify they're now untracked
git commit --amend --no-edit  # amend the last commit
```

---

## Check Severity Levels

| Check | Severity | Blocks Push | Allows Override |
|-------|----------|-------------|-----------------|
| API Keys & Tokens | **HIGH** | ✅ Yes | ❌ No |
| Hardcoded Credentials | **HIGH** | ✅ Yes | ❌ No |
| .gitignore Coverage | **MEDIUM** | ✅ Yes | ❌ No |
| Large Files (>100MB) | **MEDIUM** | ✅ Yes | ❌ No |
| Cache & Temp Files | **MEDIUM** | ✅ Yes | ❌ No |

**Important**: There are **no overrides** or `--force` flags. If checks fail, the root cause must be addressed before push.

---

## Execution Environment

### Pre-Push Hook

The policy is enforced via a **git pre-push hook** located at:

```
.git/hooks/pre-push
```

When you execute `git push origin <branch>`:

1. **Before** any data reaches GitHub, Git triggers the `.git/hooks/pre-push` script
2. The script calls `.claude/scripts/pre-push-check.sh` with the target remote and branch
3. All 5 checks execute in sequence
4. If any check FAILS → push is **blocked** and error message is displayed
5. If all checks PASS → push is **allowed** to proceed

### Staged vs Committed Files

The pre-push hook checks **only staged files** (files in `git add`), not the entire history. This means:

✅ **Checked**: Files you've explicitly staged with `git add`  
❌ **Not checked**: Previously committed files (they can't be in future commits)  
⚠️ **Watch out**: Amending commits or using `git add -A` can re-stage old files

---

## Typical Workflow

### Normal (Passing) Workflow

```bash
# 1. Make changes to a feature
echo "new feature code" >> src/feature.ts
git add src/feature.ts

# 2. Commit with clear message
git commit -m "feat: add new feature description"

# 3. Push to GitHub
git push origin feature-branch
#    ↓
#    Pre-push hook runs 5 checks
#    ✅ All checks PASS
#    ↓
#    Push succeeds, commit is now on GitHub

# 4. Create a pull request or merge to main
```

### Blocked (Failing) Workflow

```bash
# 1. Accidentally add a secret file
echo "password=12345" >> config.local.ts
git add config.local.ts

# 2. Commit
git commit -m "feat: update config"

# 3. Try to push
git push origin feature-branch
#    ↓
#    Pre-push hook runs Check #2 (Hardcoded Credentials)
#    ❌ Check FAILS: "Found potential secret in: config.local.ts"
#    ↓
#    Push is BLOCKED
#    Error message displayed to user
#    ↓
#    Push does NOT reach GitHub

# 4. Fix the issue
git reset HEAD config.local.ts
git checkout -- config.local.ts
# OR
# Edit config.local.ts to remove the secret, then:
git add config.local.ts
git commit --amend --no-edit

# 5. Retry push
git push origin feature-branch
#    ↓
#    Pre-push hook runs again
#    ✅ All checks PASS
#    ↓
#    Push succeeds
```

---

## Commit Message Standards

All commits pushed to GitHub must have **clear, meaningful messages** that describe the *why* and *what*:

### Format

```
<type>(<scope>): <subject>

<body>
```

### Types

- `feat`: A new feature
- `fix`: A bug fix
- `refactor`: Code refactoring without feature/fix changes
- `docs`: Documentation updates
- `test`: Test additions or fixes
- `chore`: Maintenance, dependency updates, tooling
- `perf`: Performance improvements

### Examples

✅ Good:
```
feat(design-registry): add mental-health-b2c vertical patterns
fix(pre-push-check): improve credential detection regex
docs(github-policy): document pre-push safety checks
```

❌ Bad:
```
update
stuff
fix bug
working on github policy
```

---

## Rollback & Recovery

If a commit needs to be removed from GitHub after a push:

### Option 1: Revert (Safe, Preserves History)

```bash
# Find the commit to remove
git log --oneline -n 10

# Revert the commit (creates a new commit that undoes it)
git revert <commit-hash>

# Push the revert commit
git push origin main
```

### Option 2: Reset (Destructive, Rewrites History)

⚠️ **Only use this if the commit hasn't been pulled by others**:

```bash
# Reset to the commit BEFORE the one you want to remove
git reset --soft <previous-commit-hash>

# OR hard reset (be careful!)
git reset --hard <previous-commit-hash>

# Force push (overwrites GitHub history)
git push origin main --force
```

---

## Disabling the Policy (Emergency Only)

If the policy is blocking legitimate work:

### Temporarily Bypass

```bash
# Push without running the pre-push hook
git push origin <branch> --no-verify
```

⚠️ **Warning**: This skips ALL checks. Only use if:
- The blocked commit is absolutely safe
- You've manually verified all 5 checks
- You're in an emergency situation

### Permanently Disable

```bash
# Remove the pre-push hook
rm .git/hooks/pre-push

# Re-enable it later
bash .claude/GITHUB-POLICY-SETUP.md
```

---

## Monitoring & Audit Trail

Every push is logged in:

```
.git/logs/refs/remotes/origin/main
```

View the history:
```bash
git log --oneline -n 20
git log --oneline --grep="feat"  # filter by type
git log --author="<your-name>"   # filter by author
```

---

## Policy Updates

This policy may be updated to:
- Add new vertical-specific checks
- Adjust thresholds (e.g., large file size limit)
- Add additional pattern detection for emerging threats
- Refine commit message standards

Updates are documented in this file with the **Last Updated** date.

---

## FAQ

**Q: Can I push binary files?**  
A: Only if they're under 100MB and NOT cache/temp files. Recommend using `.gitignore` instead.

**Q: What if I need to commit a .env file for documentation?**  
A: Create `.env.example` instead with placeholder values, and add `.env` to `.gitignore`.

**Q: Can I bypass the checks?**  
A: Only with `--no-verify`, which is an emergency override. It's logged and should be avoided.

**Q: Who enforces this policy?**  
A: The git pre-push hook enforces it automatically. No manual review needed for basic checks.

**Q: What if a check is too strict?**  
A: Report it, and we'll adjust the thresholds or patterns in `.claude/scripts/pre-push-check.sh`.

---

## Support & Escalation

If you encounter issues with the policy:

1. **Check the pre-push output** — error messages explain exactly what failed
2. **Review the remediation steps** in this document for your check type
3. **Fix the staged files** before retrying the push
4. **If the policy is broken** — open an issue or escalate to the ATLAS maintainers

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2026-05-14 | Initial release: 5 core security checks, pre-push hook, full documentation |


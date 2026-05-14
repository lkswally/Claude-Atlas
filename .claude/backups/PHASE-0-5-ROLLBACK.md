# Phase 0.5 Rollback Instructions

**Backup Date**: 2026-05-14 09:01:33  
**Backup Location**: `~/.claude/backups/phase-0-5-pre-20260514-090133/`  
**Files Added in Phase 0.5**: ~65 files, 1.2M total  
**Time to Rollback**: < 2 minutes  

---

## Quick Rollback (if framework is broken)

If the Design Registry Framework is causing issues and you need to revert immediately:

### Option 1: Delete framework directory (fastest)
```powershell
Remove-Item -Path "C:\Users\Lucas\.claude\design-registry" -Recurse -Force
```

**Effect**: Removes all framework files and verticals. Projects without `project-metadata.json` will be unaffected. evidence-collector.md will skip Design Registry gate checks (graceful fallback).

### Option 2: Restore from full backup (safest)
```powershell
# This restores the ENTIRE .claude directory to pre-Phase-0-5 state
Copy-Item -Path "C:\Users\Lucas\.claude\backups\phase-0-5-pre-20260514-090133\*" -Destination "C:\Users\Lucas\.claude\" -Recurse -Force

# Verify restoration
Get-ChildItem "C:\Users\Lucas\.claude\design-registry" -ErrorAction SilentlyContinue
# Should return: Directory not found (pre-Phase-0-5 state)
```

**Effect**: Reverts ALL changes, including evidence-collector.md updates. Equivalent to time-travel to pre-Phase-0-5.

---

## Step-by-Step Rollback (preserves other work)

If you want to rollback Phase 0.5 while keeping other improvements:

### 1. Backup current state (safety first)
```powershell
$timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
$backupDir = "C:\Users\Lucas\.claude\backups\phase-0-5-post-$timestamp"
New-Item -ItemType Directory -Path $backupDir -Force | Out-Null
Copy-Item -Path "C:\Users\Lucas\.claude\design-registry" -Destination "$backupDir\design-registry" -Recurse -ErrorAction SilentlyContinue
Write-Host "Current Phase 0.5 state backed up to: $backupDir"
```

### 2. Revert evidence-collector.md to pre-Phase-0-5 version

The pre-Phase-0-5 evidence-collector.md is in the backup without sections 4g (Design Registry Gates) and the updated Return Envelope.

**Option A — Use backup version**:
```powershell
Copy-Item -Path "C:\Users\Lucas\.claude\backups\phase-0-5-pre-20260514-090133\agents\evidence-collector.md" -Destination "C:\Users\Lucas\.claude\agents\evidence-collector.md" -Force
```

**Option B — Manual removal of Phase 0.5 sections**:

In `~/.claude/agents/evidence-collector.md`, remove:
- Section **4g. Design Registry Framework Gates** (lines ~427-500)
- Updated Return Envelope field `DESIGN_REGISTRY_GATES:` (add back older version if saved)

### 3. Delete design-registry directory
```powershell
Remove-Item -Path "C:\Users\Lucas\.claude\design-registry" -Recurse -Force
```

### 4. Verify rollback
```powershell
# These should NOT exist after rollback:
Test-Path "C:\Users\Lucas\.claude\design-registry" 
# Expected: False

Test-Path "C:\Users\Lucas\.claude\design-registry\framework\pattern-extraction-schema.json"
# Expected: False

Test-Path "C:\Users\Lucas\.claude\design-registry\verticals\mental-health-b2c"
# Expected: False
```

---

## What Gets Deleted in Rollback

### Directories & Files Added
```
~/.claude/design-registry/
├── framework/
│   ├── pattern-extraction-schema.json       (59 lines)
│   ├── vertical-config-schema.json          (88 lines)
│   └── stage-gates-schema.json              (98 lines)
├── verticals/
│   └── mental-health-b2c/
│       ├── patterns.json                    (145 lines)
│       ├── config.json                      (180 lines)
│       └── benchmarks.md                    (~300 lines)
├── projects/
│   └── sample-therapy-app/
│       ├── project-metadata.json
│       └── evaluation-checklist.md          (~200 lines)
└── presets/                                 (placeholder directory)
```

### Files Modified
- `~/.claude/agents/evidence-collector.md` — added sections 4g, updated Return Envelope

---

## Rollback Validation Checklist

After rolling back, verify:

- [ ] `~/.claude/design-registry/` directory does NOT exist
- [ ] `~/.claude/agents/evidence-collector.md` reverted (no section 4g, old Return Envelope)
- [ ] No broken imports in agents (evidence-collector should not reference design-registry)
- [ ] Sample project NOT broken (if you created external projects using framework)
- [ ] Git status clean (no Phase 0.5 commits if using version control)

---

## If a Project Uses Framework (After Rollback)

If you created a project with `project-metadata.json` referencing the framework:

```json
{
  "vertical": "mental-health-b2c",
  "stage": "mid_stage"
}
```

After rollback:

1. **evidence-collector will gracefully skip** design gates (section 4g checks for `project-metadata.json`, finds vertical not found in `~/.claude/design-registry/`, continues without gate validation)
2. **Project still works** — just without framework validation
3. **To restore framework** — either:
   - Re-run Phase 0.5 setup, OR
   - Restore from the per-phase backup (`phase-0-5-post-<timestamp>/`)

---

## Recovery from Corrupted Framework

If the framework files are **malformed** (JSON parse error, incomplete schemas):

### Quick Fix (patch single file)
```powershell
# If only one vertical config is broken:
Remove-Item -Path "C:\Users\Lucas\.claude\design-registry\verticals\mental-health-b2c\config.json" -Force
# Restore from backup:
Copy-Item -Path "C:\Users\Lucas\.claude\backups\phase-0-5-pre-20260514-090133\design-registry\verticals\mental-health-b2c\config.json" -Destination "C:\Users\Lucas\.claude\design-registry\verticals\mental-health-b2c\config.json" -Force
```

### Full Framework Restore
```powershell
# Delete corrupted framework
Remove-Item -Path "C:\Users\Lucas\.claude\design-registry" -Recurse -Force
# Restore from backup
Copy-Item -Path "C:\Users\Lucas\.claude\backups\phase-0-5-pre-20260514-090133\design-registry" -Destination "C:\Users\Lucas\.claude\design-registry" -Recurse -Force
```

---

## Rollback Impact Analysis

| Component | Impact | Notes |
|-----------|--------|-------|
| ATLAS pipeline | ✅ No impact | Phase 0-4 unaffected, gates are additive to Fase 3/4 QA |
| vibecoding reference | ✅ No impact | Framework was inspired by vibecoding, not dependent on it |
| Projects using framework | ⚠️ Validation skipped | Projects continue to work but lose design gate validation |
| evidence-collector agent | 🔄 Reverted | Section 4g removed, graceful fallback if project-metadata missing |
| Existing vertical configs | ✅ Keep | (none existed pre-Phase-0-5, so not applicable) |

---

## Backup Retention Policy

- **Pre-Phase-0-5 backup**: Keep indefinitely (Phase-0-5-pre-20260514-090133)
- **Post-Phase-0-5 backups**: Keep for 30 days as rollback snapshots, then delete (clean up older `phase-0-5-post-*` directories)
- **Per-phase backups in `~/backups/`**: Keep current + previous 2 versions of each phase

---

## Testing Rollback Procedure

**Before you need it**, test the rollback:

```powershell
# 1. Create test backup of current state
Copy-Item -Path "C:\Users\Lucas\.claude\design-registry" -Destination "C:\Users\Lucas\.claude\backups\rollback-test" -Recurse

# 2. Simulate deletion
Remove-Item -Path "C:\Users\Lucas\.claude\design-registry" -Recurse -Force

# 3. Verify deletion
Test-Path "C:\Users\Lucas\.claude\design-registry"
# Should return: False

# 4. Restore from test backup
Copy-Item -Path "C:\Users\Lucas\.claude\backups\rollback-test" -Destination "C:\Users\Lucas\.claude\design-registry" -Recurse -Force

# 5. Verify restoration
Test-Path "C:\Users\Lucas\.claude\design-registry\framework\pattern-extraction-schema.json"
# Should return: True

# 6. Clean up test
Remove-Item -Path "C:\Users\Lucas\.claude\backups\rollback-test" -Recurse -Force
```

---

## When to Rollback

Roll back Phase 0.5 if ANY of these occur:

- ❌ Framework JSON schemas are unparseable (evidence-collector fails to load config.json)
- ❌ Design gates block ALL projects regardless of stage (logic error in stage-gates-schema)
- ❌ evidence-collector crashes when evaluating gates (Engram integration broken)
- ❌ Sample project validation fails (framework doesn't work as designed)
- ❌ Pattern extraction is mis-applied to wrong vertical (need to redesign)

Do NOT roll back for:

- ✅ Individual gate rules need refinement (update config.json in place)
- ✅ New vertical needs to be added (Phase 0.5 Week 2 work)
- ✅ Benchmarks need re-analysis (update benchmarks.md in place)

---

## Post-Rollback Next Steps

After rollback:

1. **Document what went wrong** → save to Engram with `mem_save(type: "discovery", title: "Phase 0.5 rollback reason")`
2. **Refine the approach** → adjust framework schema or gate logic based on failure
3. **Re-run Phase 0.5** with fixes
4. **Test on sample project** again before approving

---

## Contact & Escalation

If rollback doesn't work or leaves system in inconsistent state:

1. **Verify backups exist**: Check `~/.claude/backups/phase-0-5-pre-20260514-090133/` (1.2M)
2. **Full system restore**: Worst-case, restore entire ~/.claude from backup
3. **Confirm ATLAS untouched**: Pipeline files in ~/.claude/{agents,contracts,backlog} should be unaffected


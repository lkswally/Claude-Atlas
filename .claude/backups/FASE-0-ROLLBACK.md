# Fase 0 Rollback Instructions

**Backup Date:** 2026-05-11 16:56 UTC  
**Backup Location:** `~/.claude/backups/fase-0-pre-20260511-165621/`

If Fase 0 needs to be rolled back, execute exactly:

## Complete Rollback (Remove All Fase 0 Changes)

```bash
# Remove contracts/ and backlog/ directories
rm -rf ~/.claude/contracts
rm -rf ~/.claude/backlog

# Verify they're gone
ls -la ~/.claude/contracts 2>&1  # Should show "No such file"
ls -la ~/.claude/backlog 2>&1    # Should show "No such file"

# Restore from backup (optional, only if needed)
cp -r ~/.claude/backups/fase-0-pre-20260511-165621/agents ~/.claude/
cp -r ~/.claude/backups/fase-0-pre-20260511-165621/hooks ~/.claude/
cp ~/.claude/backups/fase-0-pre-20260511-165621/ATLAS.md ~/.claude/
cp ~/.claude/backups/fase-0-pre-20260511-165621/intent-clarifier.md ~/.claude/

# Verify restoration
ls -la ~/.claude/agents | head -5
ls -la ~/.claude/hooks | head -5
```

## Partial Rollback (Keep One, Remove Other)

### Remove Only contracts/
```bash
rm -rf ~/.claude/contracts
```

### Remove Only backlog/
```bash
rm -rf ~/.claude/backlog
```

## Verification

After rollback, verify system state:

```bash
# Should NOT exist after rollback
ls ~/.claude/contracts 2>&1
ls ~/.claude/backlog 2>&1

# Should still exist and be unchanged
ls ~/.claude/agents | wc -l        # Should be 38
ls ~/.claude/hooks | wc -l         # Should be 14

# Backup should still be there for reference
ls ~/.claude/backups/fase-0-pre-20260511-165621/
```

## What Was Added (For Reference)

### contracts/ (5 files)
- README.md
- phase-specs.md
- approval-gates.md
- templates/phase-output-template.md
- templates/handoff-checklist.md

### backlog/ (8 files)
- README.md
- index.md
- sprints/current.md
- sprints/planned.md
- issues/open/.gitkeep
- issues/closed/.gitkeep
- templates/issue-template.md
- templates/sprint-template.md

## Notes

- Backup contains: agents/, hooks/, ATLAS.md, intent-clarifier.md, settings.json, settings.local.json
- No agents were modified during Fase 0
- No hooks were modified during Fase 0
- No Engram database touched
- No project code touched
- Rollback is safe and reversible

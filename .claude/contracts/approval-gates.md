# Approval Gates

ATLAS pauses at these checkpoints and waits for explicit user confirmation.

| Phase | Gate | What Approver Sees | Must Say |
|-------|------|-------------------|----------|
| 1 End | Tasks + Criteria | Bulleted task list with @acceptance-criteria | "Aprobada Fase 1" |
| 2 End | Architecture + Security | Tech stack, design system, security review | "Aprobada Fase 2" |
| 3 End | Code + Evidence | PR preview, test results, screenshots | "Aprobada Fase 3" |
| 4 End | Reality Check | Report: CWV, perf, security, coverage metrics | "Aprobada Fase 4" |
| 5.1 | Git Handoff | Commit message + branch name + push destination | "Aprobada Fase 5 git" |
| 5.2 | Deploy Handoff | Deploy target, environment, rollback plan | "Aprobada Fase 5 deploy" |

## What Happens If User Absent

1. ATLAS persists all state in Engram (topic_key = `{project}/{phase}`)
2. Session ends cleanly
3. Next session can resume from same checkpoint
4. No data loss, no code lost

## Overriding Approval

If gate is blocking and you want to force:
- Say: `"Fuerza {fase} sin aprobación"` — ATLAS logs override and continues
- Risky: only for testing, not production

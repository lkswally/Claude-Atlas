# Phase Contracts — ATLAS

Formalización de qué entrega cada fase del pipeline.

## Phases & Deliverables

| Fase | Output | Owner | Aprobador |
|------|--------|-------|-----------|
| **1: Planning** | tasks.md + acceptance criteria | project-manager-senior | User |
| **2: Architecture** | design system + tech stack + security review | ux-architect + security-engineer | User |
| **3: Dev + QA** | code + tests + evidence | frontend-developer + evidence-collector | User |
| **4: Certification** | reality-checker report + metrics | reality-checker | User |
| **5: Deploy** | git commit + production deploy | deployer + git | User |

## Standard Handoff Checklist

Before agent hands off to next phase:
- [ ] Engram entry created (topic_key: `{project}/{phase}`)
- [ ] All artifacts in place
- [ ] Backup created (if code changes)
- [ ] No uncommitted changes
- [ ] Next phase prerequisites met

See phase-specs.md for details.

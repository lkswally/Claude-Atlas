# FASE 0 Execution Plan — contracts/ + backlog/
> Plan de ejecución mínima, con backup previo, cambios claros y rollback documentado.

---

## Objective
Crear dos directorios de gobernanza formales sin tocar código existente. Solo docs puras.

---

## Pre-Execution Checklist

- [ ] Backup completo de `~/.claude/` → `~/.claude/backups/fase-0-pre-$(date +%Y%m%d-%H%M%S)/`
- [ ] Verificar que no hay sesiones Engram activas
- [ ] Confirmar git status limpio
- [ ] Plan file presente en `~/.claude/plans/`

---

## Cambios Mínimos (Estructura Pura)

### 1. Crear contracts/ — Formalizar salidas de fase

**Ubicación:** `~/.claude/contracts/`

**Contenido exacto:**

```
contracts/
├─ README.md                    ← Introducción a contratos
├─ phase-specs.md               ← Specs de cada fase (1-5)
├─ approval-gates.md            ← Puntos de aprobación humana
└─ templates/
   ├─ phase-output-template.md  ← Template de output por fase
   └─ handoff-checklist.md      ← Checklist de handoff
```

**Qué entra en cada archivo:**

#### contracts/README.md
```markdown
# Phase Contracts — ATLAS

Especificación formal de qué entrega cada fase.

- **Fase 1** (Planning): Project tasks + acceptance criteria
- **Fase 2** (Architecture): Design system + tech stack + security review
- **Fase 3** (Dev + QA): Code + tests + evidence + security gates
- **Fase 4** (Certification): Reality check report + metrics
- **Fase 5** (Deploy): Git commit + Vercel/EAS deploy

Cada fase tiene output spec en phase-specs.md.
```

#### contracts/phase-specs.md
```markdown
# Phase Output Specifications

## Fase 1 — Planning
Output:
- Engram entry: topic_key="{project}/phase-1"
- File: tasks.md (formato: tasklist with @acceptance-criteria)
- Approval: project-manager-senior ✓

## Fase 2 — Architecture
Output:
- brand.json (si visual projects)
- architecture.md (stack, patterns, security)
- Approval: ux-architect + security-engineer ✓

## Fase 3 — Dev + QA
Output:
- /src/** (código)
- /tests/** (tests)
- evidence/ (screenshots)
- Approval: evidence-collector + code-review ✓

## Fase 4 — Certification
Output:
- reality-checker report
- Metrics: CWV, performance, security scan
- Approval: reality-checker ✓

## Fase 5 — Deploy
Output:
- Git commit + push
- Deployment to production
- Approval: user confirmation ✓
```

#### contracts/approval-gates.md
```markdown
# Approval Gates

ATLAS pauses at these points:

| Phase | Gate | Approver | Must Say |
|-------|------|----------|----------|
| 1 End | Tasks + Criteria | User | "Aprobada Fase 1" |
| 2B End | Brand + Assets | User | "Aprobada Fase 2B" |
| 4 End | Reality Check | User | "Aprobada Fase 4" |
| 5 Step 1 | Git Commit + Push | User | "Aprobada Fase 5 git" |
| 5 Step 2 | Deploy to Prod | User | "Aprobada Fase 5 deploy" |

If user absent → ATLAS persists state in Engram + closes session.
```

#### contracts/templates/phase-output-template.md
```markdown
# Phase Output Template

## Project: {project_name}
## Phase: {1-5}
## Date: {ISO 8601}
## Operator: {agent_name}

### Deliverables
- [ ] Engram entry (topic_key: {project}/{phase})
- [ ] Primary artifacts (code/docs/designs)
- [ ] Evidence (screenshots/metrics)

### Acceptance Criteria Met
- Criterion 1: ✓
- Criterion 2: ✓

### Handoff to Next Phase
- All artifacts in place: ✓
- Engram entry links documented: ✓
- Open issues filed (if any): {issues}
```

#### contracts/templates/handoff-checklist.md
```markdown
# Handoff Checklist — Phase to Phase

Before agent hands off to next phase, verify:

- [ ] Engram entry with topic_key = "{project}/{phase}"
- [ ] All outputs documented in README
- [ ] Rollback point saved (backup of pre-phase state)
- [ ] No uncommitted changes in project code
- [ ] Next phase prerequisites met

If any unchecked → agent refus handoff + flags to user.
```

---

### 2. Crear backlog/ — Estructura formal de issues

**Ubicación:** `~/.claude/backlog/`

**Contenido exacto:**

```
backlog/
├─ README.md                    ← Overview
├─ index.md                     ← Cross-project patterns
├─ issues/
│  ├─ open/
│  │  ├─ {project}-{id}.md
│  │  └─ ...
│  └─ closed/
│     ├─ {project}-{id}.md
│     └─ ...
├─ sprints/
│  ├─ current.md                ← Sprint actual
│  ├─ planned.md                ← Sprints futuros
│  └─ archive/
│     └─ sprint-{YYYY-MM}.md
└─ templates/
   ├─ issue-template.md
   └─ sprint-template.md
```

**Qué entra en cada archivo:**

#### backlog/README.md
```markdown
# ATLAS Backlog — Formal Issue Tracking

Central registry of all issues, improvements, and blockers across projects.

## Structure
- **issues/open/** — Current, unresolved issues
- **issues/closed/** — Resolved issues (archive)
- **sprints/current.md** — This sprint's focus
- **index.md** — Cross-project pattern summary

## Naming Convention
Issues: `{project}-{number}` (e.g., `reyesoft-001`, `atlas-042`)

## Integration
- Engram can query issues via `mem_search("backlog", "{project}")`
- Each issue has Engram entry linking to this file
```

#### backlog/index.md
```markdown
# Backlog Index — Cross-Project Patterns

## Open Issues by Category

### P0 (Blocking)
- None currently

### P1 (High Priority)
- See issues/open/ for details

### P2 (Medium Priority)
- See issues/open/ for details

### P3 (Low Priority)
- See issues/open/ for details

## Recurring Patterns
- **Auth/Security**: {count} issues (see tag: security)
- **Performance**: {count} issues (see tag: perf)
- **UX/Design**: {count} issues (see tag: ux)

(Updated manually per sprint)
```

#### backlog/templates/issue-template.md
```markdown
# Issue: {title}

**ID:** {project}-{number}
**Status:** open / closed
**Priority:** P0 / P1 / P2 / P3
**Created:** {ISO 8601}
**Project:** {project}

## Description
{Problem statement}

## Acceptance Criteria
- [ ] Criterion 1
- [ ] Criterion 2

## Tags
- {tag1}
- {tag2}

## Related
- Links to other issues
- Engram entries
- GitHub issues (if exists)

## Notes
{Internal notes, blocked-by relationships, etc.}
```

#### backlog/templates/sprint-template.md
```markdown
# Sprint: {name} ({YYYY-MM-DD} to {YYYY-MM-DD})

## Goals
- Goal 1
- Goal 2

## Issues in This Sprint
| ID | Title | Priority | Owner | Status |
|----|-------|----------|-------|--------|
| PROJECT-001 | ... | P1 | @agent | in-progress |

## Metrics
- Velocity: {story points}
- Completion: {%}

## Blockers
- None / List any

## Notes
{Retrospective or handoff notes}
```

#### backlog/sprints/current.md
```markdown
# Current Sprint

(Initially empty; will be populated as needed)

See sprint-template.md for structure.
```

#### backlog/sprints/planned.md
```markdown
# Planned Sprints

(Initially empty; will be populated as needed)

See sprint-template.md for structure.
```

#### backlog/issues/open/.gitkeep
(Empty file to preserve directory structure in git)

#### backlog/issues/closed/.gitkeep
(Empty file to preserve directory structure in git)

---

## Validation Checklist

After creating both directories:

- [ ] `~/.claude/contracts/` exists with 5 files (README, phase-specs, approval-gates, 2 templates)
- [ ] `~/.claude/backlog/` exists with full structure (README, index, sprints, issues, templates)
- [ ] All `.md` files are readable and have valid YAML frontmatter (if used)
- [ ] No existing agent files modified
- [ ] No hooks modified
- [ ] Engram database not touched
- [ ] Git status shows only new files (no deletions, no renames)

---

## Rollback Strategy

If something goes wrong at any point:

```bash
# Restore from backup
rm -rf ~/.claude/contracts ~/.claude/backlog
cp -r ~/.claude/backups/fase-0-pre-{timestamp}/* ~/.claude/

# Verify restoration
ls -la ~/.claude/contracts ~/.claude/backlog  # Should NOT exist
git status  # Should be clean
```

---

## Approval Before Execution

This plan is ready. Before I create contracts/ + backlog/:

**Confirm:**
- [ ] Aprobás esta estructura exacta para contracts/?
- [ ] Aprobás esta estructura exacta para backlog/?
- [ ] Querés cambios en los templates o archivos?

If all OK → ejecuto Fase 0 con backup + validación completa.

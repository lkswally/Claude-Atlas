# ATLAS Backlog — Issue Tracking

Central registry of all issues, improvements, and blockers across projects.

## Structure

- `index.md` — Summary of all open/closed issues by priority
- `issues/open/` — Current unresolved issues
- `issues/closed/` — Resolved issues (archive)
- `sprints/current.md` — This sprint's focus
- `sprints/planned.md` — Future sprints
- `templates/` — Templates for new issues

## Naming Convention

Issue files: `{project}-{number}.md`
- Example: `reyesoft-001.md`, `atlas-042.md`

## Priority Levels

- **P0** — Blocking (stop everything)
- **P1** — High (next sprint)
- **P2** — Medium (soon)
- **P3** — Low (backlog)

## Engram Integration

Issues are searchable via Engram:
```
mem_search("backlog", "{project}")
mem_search("backlog P0")
```

Each issue file links to corresponding Engram entry (if created).

## How to Use

1. Create new issue in `issues/open/{project}-{number}.md`
2. Add entry to `index.md`
3. Create Engram entry with backlog link
4. Move to `issues/closed/` when resolved

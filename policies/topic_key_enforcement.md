# Topic_key Enforcement Policy

**Requirement**: TODOS los `mem_save()` DEBEN incluir `topic_key` parameter.

## Por qué

- **Evita duplicados en reintentos**: mem_save sin topic_key crea N observaciones idénticas en Engram
- **Facilita upserts**: mem_update busca por topic_key, no por ID
- **Traceabilidad**: topic_key sigue patrón `{proyecto}/{cajon}` → fácil de buscar y audit
- **Continuidad post-compactación**: topic_key persiste incluso si Engram se compacta

## Formato obligatorio

```python
mem_save(
  title: "{proyecto} — {descripción}",
  content: "{contenido}",
  type: "decision|architecture|bugfix|discovery|pattern",
  topic_key: "{proyecto}/{cajon}",  # OBLIGATORIO
  project: "{proyecto}"
)
```

## Topic_key Pattern

- `{proyecto}/estado` — DAG state (orquestador)
- `{proyecto}/tareas` — task list (project-manager)
- `{proyecto}/tarea-{N}` — individual task result (dev agents)
- `{proyecto}/qa-{N}` — QA result (evidence-collector)
- `{proyecto}/discovery-{slug}` — discovery/learning (any agent)
- `{proyecto}/{cajon}` — genérico

## Validación de Compliance

```bash
python tools/topic_key_enforcer.py agents/
```

Returns:
- `PASS` — All agents use topic_key
- `NEEDS WORK` — X HIGH violations (mem_save sin topic_key)

## Enforcement Level

**Current**: No bloqueo. Validación via linter.
**Future** (Phase 0.6B): Rechazar mem_save sin topic_key en dispatcher.

---

**Last validated**: 2026-05-19 — 100% compliance (37 agents, 0 HIGH violations)

# Observabilidad ATLAS — Roadmap Futuro (Decisión: Deferred)

**Fecha**: 2026-05-17  
**Status**: DOCUMENTADO COMO REFERENCIA — NO IMPLEMENTAR TODAVÍA  
**Revisitar**: Después de 3-5 proyectos reales en ATLAS  

---

## DECISIÓN

✅ Guardar propuesta de observabilidad como roadmap futuro  
❌ No implementar OpenTelemetry / event-capture / dashboards ahora  
❌ No usar Observe como backend  
❌ No avanzar con automejora automática  
✅ Documentar como referencia mínima para después  

---

## CUÁNDO REVISITAR

Criterio: Ejecutar ATLAS en 3-5 proyectos reales y verificar si estos problemas aparecen:
- [ ] Diseño genérico rechazado por QA >1 vez en mismo proyecto
- [ ] QA false positives (QA rechaza, user aprueba)
- [ ] Hooks fallan silenciosamente
- [ ] Session drift Fase 1 → Fase 3
- [ ] Engram timeouts → fallback silencioso

Si ≥2 de estos se confirman → Phase 1 roadmap (30 líneas Bash, 2h).

---

## REFERENCIA MÍNIMA SI DECIDES IMPLEMENTAR

**Phase 1 bloque exacto** (cuando decidas actuar):

Archivos a crear:
- `.claude/observability-phase-1.md` (schema)
- `.claude/hooks/event-capture.sh` (5 lugares: orquestador, evidence-collector, dual-write-sync, block-no-verify, fallbacks)

Implementación:
- ~30 líneas de Bash total
- ~2 horas de setup
- Zero production risk (solo logging)

Storage:
- Phase 1: `.pipeline/events.jsonl` (append-only, local)
- Phase 2+: PostgreSQL + Grafana (solo si validados problemas)

---

## LO QUE QUEDA DOCUMENTADO

Análisis completo en sesión anterior (see CLAUDE.md history si necesario).

Key points:
- OpenTelemetry + local stack > Observe (cost/complexity)
- 4-phase roadmap: Foundation → Visibility → Classification → Assisted Improvement
- Human-in-the-loop: mejoras propostas, user aprueba, branch+PR, monitored 2w
- Riesgos mitigados: auto-loops, ruido, complejidad

---

## HOY

- **No hacer cambios**
- **ATLAS sigue sin observabilidad**
- **Volver a trabajo actual**

Revisitamos después de uso real. ✅


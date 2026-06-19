# F35 — Architecture Decision Governor Report

**Fecha:** 2026-06-19
**Base:** ATLAS v1.0.0-rc2 (post-F34 `67d5445`)
**Modo:** análisis + nuevas capacidades read-only. **Sin tocar dispatcher/runtime/agentes/CI/MCPs. Sin copiar upstream. Reversible.**

---

## ¿Por qué ATLAS no detectó antes estos problemas?

Porque tenía buenos checks de **ejecución** (CI, healthcheck, drift, release gates)
pero ninguno de **decisión**. Validaba que el código funcionara, no que el cambio
*valiera la pena* ni que los claims fueran ciertos. En concreto (ver F35.1):
- CI/quick/release pasaban en verde con claims documentales **falsos** en README.
- No medía costo de contexto → el boot cost (CLAUDE.md 8.7K) fue invisible hasta una
  comparación externa.
- No tenía señal de **sobreingeniería** ni de **deriva de dependencias**.
- Ejecutaba la agenda de cada fase sin aplicar fricción crítica ("¿hace falta?").

## ¿Qué clase de problemas detecta ahora?

- **Costo de contexto / always-on** → Boot Profiler (F29).
- **God-files, duplicación, oversized, entropía** → Architecture Audit (F31), Score 86.
- **Carga selectiva por intención** → Knowledge Resolver (F33/F34).
- **Calidad de decisión** → Architecture Decision Governor (F35): clasifica cualquier
  propuesta en ACCEPT / ACCEPT_WITH_LIMITS / DEFER / REJECT / NEEDS_EVIDENCE /
  NEEDS_HUMAN_APPROVAL por evidencia y riesgo, y marca dependencias/externos/runtime/
  boot/sobreingeniería.

## ¿Qué clase de problemas aún NO detecta?

- **Honestidad documental automática**: validar que un claim del README sea cierto
  sigue siendo manual (F27 fue manual). Candidato: un linter de claims absolutos.
- **Necesidad real vs. deseo**: el governor da señal, pero el juicio de "vale la pena"
  sigue requiriendo criterio humano/ATLAS.
- **Deriva de dependencias en código** (un `import` nuevo no dispara alarma).
- **Trazabilidad de decisiones**: no hay ADR automático del por qué de cada accept/reject.

## ¿Cómo evitar que ATLAS vuelva a obedecer ciegamente?

1. **Gate de decisión antes de implementar:** correr `architecture_decision.py` sobre
   toda propuesta no trivial; si da NEEDS_HUMAN_APPROVAL/NEEDS_EVIDENCE/REJECT, **no
   ejecutar** sin resolver eso primero.
2. **Verificar claims antes de aceptarlos** (regla `unverified_claims` en la policy).
3. **Preferir no tocar nada** cuando riesgo > impacto o el área es estable y el
   beneficio es cosmético (`prefer_no_change_when`).
4. **Exigir comparación externa** antes de afirmar paridad/superioridad o adoptar un
   patrón upstream.
5. ATLAS propone el próximo paso por evidencia (abajo), no espera la agenda externa.

## ¿Qué puede rescatar de claude-vibecoding sin copiarlo?

(Detalle en `F35-VIBECODING-COMPARISON-REVIEW.md`.) Solo **doctrina**, redactada de cero:
- **ADOPT**: Modo Diagnóstico (read-only audit), Simplicity First (output TL;DR-first).
- **ADAPT**: No-JS Render Audit (gate SEO/a11y, modo warn).
- **DEFER**: design-data self-contained (medir antes), engram-cloud-sync (caso real).

## ¿Qué debe rechazar?

- **zen-delegate** (modelos Go externos), **external-skills** (`npx skills add`,
  cadena de suministro no auditada), y el **segundo stack de observability JS**
  (healthcheck/drift/mcp-registry .js) que duplica el Python existente.

## Próximo paso recomendado — por ATLAS, no por el usuario

> Decisión propia, con evidencia:

**No agregar features. Endurecer la honestidad documental.** El mayor riesgo residual
no es el costo de contexto (ya resuelto F29–F34) ni la arquitectura (Score 86) — es
que un claim falso vuelva a pasar verde, como ocurrió pre-F27. Por eso ATLAS propone
como **F36** un **Claim Linter** (read-only): detectar afirmaciones absolutas
("all/never/always/fully/no agent…") en README/CLAUDE.md/docs y exigir evidencia o
suavizado, integrado como check WARN-only del healthcheck.

Ranking de alternativas (governor):
1. **F36 Claim Linter** — ACCEPT_WITH_LIMITS (docs/tests/check, sin runtime). **Recomendado.**
2. Adoptar Modo Diagnóstico + Simplicity First (doctrina) — ACCEPT_WITH_LIMITS.
3. No-JS Render Audit — ADAPT, valor medio.
4. **No** atacar design-data / cloud-sync / zen-delegate ahora (DEFER/REJECT).

Si no hay señal nueva, la opción de mayor valor/menor riesgo es **F36**; en su defecto,
**no tocar nada** es una decisión válida (el sistema está estable y verde).

---

## Entregables F35

- `docs/F35-SELF-GOVERNANCE-AUDIT.md` — cómo decidió ATLAS en F13–F34.
- `docs/F35-VIBECODING-COMPARISON-REVIEW.md` — review estricto vs ATLAS actual.
- `config/architecture.decision-policy.yaml` — policy formal (6 estados, reglas, gates).
- `tools/architecture_decision.py` — governor CLI read-only.
- `_qa/bloque-F35-architecture-decision-governor.py` — 10 tests.
- Este reporte.

## Validación

| Check | Resultado |
|-------|-----------|
| F35 governor suite | 10/10 PASS |
| Architecture Score | 86/100 |
| Quick / Release | (ver F35.7) |
| Healthcheck / secrets | HEALTHY / exit 0 |
| Runtime/dispatcher | sin cambios |

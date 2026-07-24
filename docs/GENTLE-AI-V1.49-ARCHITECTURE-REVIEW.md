# Gentle AI v1.49.0 — Safe Architecture Review

**Fecha:** 2026-07-24
**Release analizada:** https://github.com/Gentleman-Programming/gentle-ai/releases/tag/v1.49.0 (read-only)
**Comparada contra:** ATLAS `main` @ `0b21466`, **v1.0.0-rc2**
**Licencia externa:** **MIT** (reuso permitido con atribución) — aun así se prefiere
reimplementación independiente de ideas, sin copiar código.
**Modo:** análisis + Governor. **Nada se incorpora automáticamente.**

> **VEREDICTO: NO_CHANGE.** Los patrones de valor de v1.49.0 ya están cubiertos por
> mecanismos existentes de ATLAS (retry budget, file-hash caching, delegation stop rules,
> file-change declaration). No hay fricción observada que justifique una capa nueva sobre
> un v1.0 recién congelado. Los patrones con dependencia externa (OpenCode, Pi CodeGraph)
> son REJECT por política. Único artefacto de este review: este documento.

---

## 1. Baseline (protegido, verificado en este review)

| Métrica | Valor |
|---------|-------|
| Commit inicial | `0b21466` (sync local=origin) |
| compileall (tools/core/_qa) | exit 0 |
| Healthcheck | HEALTHY — 24 PASS / 2 WARN / 0 FAIL / 26 |
| Quick | **36/36 PASS** (55.4s) |
| Release | **39/39 PASS** (verificado en CI del commit `0b21466`) |
| Secrets | exit 0, 0 filtrados |
| Claim linter | 0 HIGH / 0 CRITICAL (8 LOW, 42 MEDIUM) |
| Boot always-on | 1841 tok / 2500 budget |
| git diff --check (ATLAS) | limpio |

Sin FAIL preexistente. Working tree: solo cambios del proyecto externo `lucas-rojo-web/*`
(preexistentes, preservados, fuera de scope). No se mezcló nada.

## 2. Contenido analizado (read-only)

v1.49.0 "focuses on tightened boundaries around delegation, exploration, and code review":
- **#1106 Review Once, Fix Once, Move Forward** — bounded review lifecycle
  (scope → implement → test → one review → freeze → one fix → targeted verify → continue).
- **#1098 Durable Pre-Push Review Authority** — content-bound review receipts que
  sobreviven al commit si el contenido no cambió.
- **#1100 Native OpenCode Delegation** — exploración/ejecución delegada a runtime externo OpenCode.
- **#1101 Optional Pi CodeGraph Lifecycle** — provider externo CodeGraph (install/sync/uninstall).

## 3. Patrones identificados (12 solicitados)

Frozen review scope · immutable findings ledger · one-fix budget · targeted post-fix
validation · late findings as follow-ups · contradiction escalation · content-bound
receipts · provenance/validation evidence · OpenCode delegation · CodeGraph · model/agent
changes · new dependencies. Los primeros 8 pertenecen al Bounded Review Lifecycle (#1106/#1098);
9–10 son dependencias externas (#1100/#1101); 11–12 no aplican a una adopción de ATLAS.

## 4. Matriz de decisión

| Patrón | Problema real | ATLAS ya lo tiene | Gap confirmado | Beneficio | Costo | Riesgo | Decisión |
|--------|---------------|-------------------|----------------|-----------|-------|--------|----------|
| Frozen review scope | scope creep en re-review | **Sí** — `verify_declared_files` (1A.16: declarado ⊇ git diff) + forbidden paths por hooks | Parcial | bajo | medio | **NO_CHANGE** |
| Immutable findings ledger | findings mutan post-review | **Sí** — Return Envelope + Engram append-only (1I.1) | Parcial | bajo | medio | **NO_CHANGE** |
| One-fix correction budget | fixes ilimitados | **Sí** — budget de 3 reintentos dev↔QA | No (existe budget) | bajo | bajo | **NO_CHANGE** |
| Targeted post-fix validation | revalidar todo | **Sí** — `file_hash_cache.py` (skip archivos sin cambio, ~70-80% ahorro) | No | — | — | **NO_CHANGE** |
| Late findings → follow-ups | re-review descubre scope nuevo | Parcial — delegation stop rules (`fresh_review_recommended` escala, no auto-loop) | Parcial | medio | medio | **NO_CHANGE** |
| Contradiction escalation | loop en vez de escalar | **Sí** — stop rules (`escalation_needed`) + Engram `mem_judge` | No | — | — | **NO_CHANGE** |
| Content-bound review receipts | re-review antes de push | **No** (novel) | Sí | teórico | medio | **DEFER** |
| OpenCode delegation | — | No | — | — | alto (dep externa) | **REJECT** |
| Pi CodeGraph | — | Explore/grep | — | no medido | alto (dep externa) | **REJECT** |

## 5. Gaps reales de ATLAS

Sólo uno **no-duplicativo**: **content-bound review receipts** (#1098) — un receipt ligado
a hashes de contenido que sobrevive al commit para evitar re-review antes del push. ATLAS
tiene evidence bundles + gate "QA antes de push", pero no un receipt hash-bound persistente.
**Sin fricción observada:** ningún proyecto de ATLAS registró un incidente de re-review
costoso antes de push. El beneficio es teórico.

## 6. Mejoras implementadas

**Ninguna de código/runtime.** Único artefacto: este documento (registro de decisión).

## 7. Mejoras rechazadas / diferidas

- **REJECT:** OpenCode delegation (#1100), Pi CodeGraph (#1101) — dependencia/runtime externo.
  Governor: **NEEDS_HUMAN_APPROVAL** (risk 3/5). §11 los prohíbe explícitamente en este review.
- **DEFER:** content-bound review receipts (#1098) — idea válida, beneficio teórico, sin
  fricción observada; se reconsidera si aparece un costo de re-review medible.
- **NO_CHANGE:** el resto del Bounded Review Lifecycle — ya cubierto por ATLAS.

## 8. Costo-beneficio

Implementar el Bounded Review Lifecycle (aun en shadow) exige contract + tool + instrumentación
+ tests + docs — trabajo real sobre un v1.0 recién congelado — para medir un beneficio del cual
**no hay evidencia de fricción**. El core ya está cubierto (retry budget, hash-cache, stop rules,
file-change declaration). Beneficio neto de adoptar: **negativo/nulo** hoy. Beneficio de
documentar la decisión: **positivo** (evita re-litigar y deja el gap trazado para el futuro).

## 9. Impacto en tokens

Cero. Cambio docs-only; boot always-on permanece en 1841 tok (sin tocar CLAUDE.md, sin ref nueva).

## 10. Impacto en runtime

Cero. No se tocó dispatcher, agentes, hooks, contratos, CI ni configuración.

## 11. Seguridad

Sin impacto. No se agregan dependencias, superficies externas ni permisos. REJECT de OpenCode/
CodeGraph evita precisamente ampliar la superficie de confianza.

## 12. Pilotos

No aplica (NO_CHANGE). No se activó shadow mode: §4 exige comprobar que ATLAS carece de la
garantía antes de implementar; la comprobación mostró cobertura sustancial → no se pilotea.

## 13. Tests

No se añadió código ⇒ sin tests nuevos. Validación proporcional (docs-only): claim linter +
healthcheck + diff-check + compileall.

## 14. Rollback

Trivial: `git revert` de un commit docs-only. Sin estado, sin migración, sin runtime.

## 15. Aprendizajes

1. gentle-ai v1.49.0 es **MIT** (a diferencia de engram/vibecoding, PolyForm-NC) — el barrier
   de licencia no aplica, pero la decisión de arquitectura no cambia.
2. El Bounded Review Lifecycle es un **buen patrón**, pero su valor central ya vive en ATLAS
   distribuido (hash-cache = targeted validation, retry budget = fix budget, stop rules =
   escalation, file-change declaration = frozen scope).
3. Coherente con la política de mantenimiento v1.0 recién commiteada: **no se agrega una fase
   de auto-mejora sin fricción real observada.**

## 16. Riesgos residuales

Ninguno introducido (cambio docs-only). Riesgo de **no** adoptar: si en el futuro un proyecto
sufre re-review costoso antes de push, reconsiderar los receipts hash-bound (#1098) como ADAPT
del Evidence Bundle existente — no como sistema nuevo.

## 17. Recomendación final

**NO_CHANGE.** ATLAS ya cubre el núcleo del Bounded Review Lifecycle; el único gap real
(content-bound receipts) tiene beneficio teórico y ninguna fricción observada, y las piezas
con dependencia externa son REJECT por política y por el Governor. Adoptar cualquier cosa aquí
contradiría la política de mantenimiento de v1.0 (solo cambios nacidos de fricción real).
Se registra el patrón como **DEFER** para cuando exista un incidente medible.

**Disparadores para reconsiderar (evidencia futura):**
- Re-review antes de push que reprocesa archivos sin cambios → receipts hash-bound (#1098).
- Loop de QA que redescubre scope entre reintentos → frozen-scope ledger explícito.
Hasta entonces: **NO_CHANGE**.

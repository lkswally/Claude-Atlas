# ATLAS Autonomy Improvement V2 — Improvement A: Deterministic Security Backstop

**Fecha:** 2026-09-09
**Baseline:** `docs/AUTONOMY-BENCHMARK-V1.md` (frozen, no modificado)
**Commit inicial:** `3b89d16` (main, sync con origin, CI success)
**Alcance de esta ejecución:** exclusivamente Improvement A. No se avanzó a
Failure Learning ni a ninguna otra mejora.

---

## Gap

**Security = 18.8%** (1.5/8 puntos, rubrica congelada). 6 de 8 fixtures
reales sin deteccion: `eval()`, SQL injection, CORS inseguro, autorizacion
faltante, patron IDOR, upload inseguro. `security-engineer` (unico agente
con juicio semantico) solo se invoca en Fase 2 del pipeline completo,
ausente del modo "Claude normal" (default para la mayoria del trabajo).

## Baseline (protegido antes de modificar)

| Check | Resultado |
|-------|-----------|
| HEAD | `3b89d16`, sync con origin, CI success |
| Working tree | Solo `lucas-rojo-web/*` preexistente (externo, no tocado) |
| Healthcheck | 24 PASS / 2 WARN / 0 FAIL |
| Quick | 38/38 PASS |
| Release | 41/41 PASS |
| Secrets | limpio |
| Claim linter | 0 HIGH / 0 CRITICAL |
| Boot | 1841 tokens always-on |

Sin FAIL preexistente — la mejora no se mezcló con ninguna reparación.

## Design

Arquitectura exacta del pedido:

```text
Code Change -> Security Backstop -> Risk Signals -> Verification Router -> Security Agent si corresponde
```

El backstop detecta, no corrige, no decide arquitectura, no genera patches,
no sustituye a security-engineer — **"FIND, DON'T FIX"**.

**Decisión de diseño central: reutilizar, no crear.** `.claude/hooks/quality-gate.js`
ya es exactamente el backstop correcto — corre en cada `Write`/`Edit` de JS/TS,
ya es WARN-only/fail-open, ya tiene arquitectura de `PATTERNS` basada en regex.
Se extendió ese mismo archivo con 7 reglas nuevas en vez de construir un
scanner separado. Sin AST, sin parser nuevo, sin dependencia SAST externa —
regex deliberadamente **angostas** para evitar falsos positivos masivos
(instrucción explícita del pedido).

**Reglas implementadas** (cada una con `id`/`category`/`confidence` estable
para el schema `security_signals` documentado):

| id | Categoría | Patrón (resumen) | Por qué es angosto |
|----|-----------|-------------------|---------------------|
| SEC-EVAL-001 | code_execution | `eval(` / `new Function(` | `\beval\s*\(` no matchea `evaluate(` (Playwright) |
| SEC-CMDI-001 | injection | `child_process.exec(` + concat | Requiere calificador `child_process`/`cp` — excluye `RegExp.exec()`, el patrón más común que colisionaría |
| SEC-SQLI-001 | injection | `.query()`/`.raw()` con SQL + concat | Query parametrizada (`?`, params separados) no matchea |
| SEC-XSS-001 | xss | `innerHTML=`/`dangerouslySetInnerHTML`/`v-html` | Solo si el RHS no es un literal estático |
| SEC-CORS-001 | access_control | `origin:'*'` + `credentials:true` cercanos | Cualquiera de los dos solo, sin el otro, no dispara |
| SEC-TLS-001 | crypto | `rejectUnauthorized:false` / `NODE_TLS_REJECT_UNAUTHORIZED=0` | Patrón único, sin ambigüedad real |
| SEC-UPLOAD-001 | path_traversal | escritura de archivo con `.originalname`/`.name` directo | Filename saneado (variable propia) no matchea |

**Deliberadamente NO implementado:** missing-authorization e IDOR genéricos.
Son problemas de **ausencia** (negative-space) — detectar que un route
handler *no tiene* un chequeo de permisos requiere entender intención de
negocio, no un patrón de texto. Un regex ingenuo aquí generaría ruido
masivo (la mayoría de rutas con `:id` legítimamente no necesitan
autorización por-objeto). Quedan, correctamente, a cargo de
`security-engineer`. Esto se documenta como límite honesto, no como
cobertura fallida.

**Output estructurado:** cada hallazgo se agrega (además del WARN existente
por stderr) a `.claude/logs/security-signals.jsonl` (gitignored, mismo
patrón que `cost-tracker.js`/`session-summary.js`) con el schema:
`{timestamp, id, category, severity, path, line, evidence, confidence, msg}`.

## Governor

```text
DECISION: NEEDS_HUMAN_APPROVAL   (rule: security)
risk: 3/5   impact: 1/5
reason: Security-sensitive — never auto-accept; human approval required.
```

El Governor marcó esto como no-auto-implementable, per su propia regla
("security" es una señal de hard-block, no un heurístico suave). Se
presentó el plan exacto (reglas, archivo, schema, límite honesto de
missing-auth/IDOR) al usuario y se obtuvo aprobación explícita antes de
tocar código — consistente con §27 del propio pedido ("Solo implementar
autónomamente si risk <= LOW/MEDIUM controlado").

## Implementation

- `.claude/hooks/quality-gate.js` (SOT) — 7 reglas nuevas + logging JSONL.
- `hooks/quality-gate.js` (dist) — sincronizado vía `tools/sync_dist.py`
  (bug propio detectado por `bloque-F10-sot-drift` tras el primer intento
  de commit — corregido antes de continuar, ver Self-Correction abajo).
- `_qa/bloque-security-backstop.py` (nuevo) — 17 tests.
- `config/test.registry.yaml` — registro del nuevo suite.

## Tests

**7 true positives** (una por regla, usando fixtures nuevos + los 4
fixtures EXACTOS originales del benchmark para SEC3/4/5/8) — 7/7 detectados.

**8 false-positive-avoidance** (`RegExp.exec()`, `page.evaluate()`,
query parametrizada, HTML estático, HTML estático con espacios múltiples,
CORS sin wildcard, filename saneado, TLS habilitado) — 8/8 correctamente
silenciosos.

**Falso positivo real encontrado y corregido durante el desarrollo:** el
lookahead negativo de SEC-XSS-001 (`(?!['"`])`) era vulnerable a
backtracking de `\s*` — el motor de regex podía reintentar con cero
espacios consumidos, dejando el lookahead frente al espacio (que
trivialmente no es una comilla) en vez de frente a la comilla real,
dejando pasar un `el.innerHTML = "texto estático";` como si fuera
peligroso. Corregido agregando `\s` al conjunto negativo del lookahead.
Test de regresión específico agregado (`FP: static innerHTML, multiple
spaces`).

**Falsos negativos conocidos (documentados, no ocultos):**
- missing-authorization / IDOR genérico — fuera de alcance por diseño.
- Interpolación en template literals hacia innerHTML (`` `${x}` ``) — la
  misma clase de límite que un literal de comillas simples/dobles; no se
  intentó resolver para no reintroducir complejidad de lookahead tras el
  bug ya encontrado.

`_qa/bloque-security-backstop.py`: **17/17 PASS**.

## Benchmark delta (Security dimension únicamente — benchmark V1 sin modificar)

| Caso | Antes | Después |
|------|-------|---------|
| SEC1 (secret) | PARTIAL | PARTIAL (sin cambio) |
| SEC2 (dangerous cmd) | PASS | PASS (sin cambio) |
| SEC3 (eval) | FAIL | **PARTIAL** |
| SEC4 (SQLi) | FAIL | **PARTIAL** |
| SEC5 (CORS) | FAIL | **PARTIAL** |
| SEC6 (missing auth) | FAIL | FAIL (fuera de alcance, honesto) |
| SEC7 (IDOR) | FAIL | FAIL (fuera de alcance, honesto) |
| SEC8 (upload) | FAIL | **PARTIAL** |

```yaml
security_score:
  before: 18.75   # 1.5/8, rubrica congelada
  after:  43.75   # 3.5/8, MISMA rubrica (detectado-no-bloqueado = PARTIAL,
                  # igual criterio ya aplicado a SEC1 — sin inventar un
                  # estándar más generoso para las reglas nuevas)
  delta:  +25.0

autonomy_score:
  before: 69.9
  after_estimated: 72.4   # +2.5 puntos ponderados (25.0 * 10% weight)
  delta: +2.5
```

Nota de honestidad: SEC3/4/5/8 se puntuaron PARTIAL, no PASS, porque el
backstop sigue siendo WARN-only (no bloquea) — exactamente el mismo criterio
que ya degradó SEC1 a PARTIAL en el benchmark original. Puntuarlas PASS
habría inflado el resultado con un estándar distinto al ya congelado.

**Ninguna otra dimensión fue re-medida** — el cambio está aislado a un hook
de contenido JS/TS sin relación con delegación, model selection,
self-correction, learning o human-intervention. No hay mecanismo plausible
de regresión en esas dimensiones y Quick/Release/Healthcheck confirman
comportamiento idéntico al baseline salvo la adición esperada.

## Self-Correction real durante esta implementación (evidencia, no simulación)

Al commitear por primera vez, `bloque-F10-sot-drift` (suite existente, no
tocada) detectó que había editado `.claude/hooks/quality-gate.js` (SOT) sin
sincronizar `hooks/quality-gate.js` (dist). Root cause identificado
inmediatamente (olvidé `tools/sync_dist.py` tras el edit), fix aplicado
(`python tools/sync_dist.py`), revalidado (quick 39/39 tras el fix) — sin
intervención humana en el diagnóstico. Regla del programa (§31) respetada:
observar → reproducir → root cause → fix → test de regresión → verificar →
(recién ahora) reportar, sin usar el error para modificar arquitectura.

## Validación final

| Check | Resultado |
|-------|-----------|
| `atlas_healthcheck.py` | 24 PASS / 2 WARN / 0 FAIL |
| `run_all.py --quick` | 39/39 PASS (estable en 4/5 corridas locales; 1 corrida con un FAIL no-reproducible en una suite distinta a la nueva, mismo patrón de flakiness local ya observado y auto-resuelto en tareas previas de esta sesión — CI real es el árbitro decisivo, ver abajo) |
| `run_all.py --release` | 41/41 PASS |
| `secrets_check.py` | limpio |
| `claim_linter.py --summary` | 0 HIGH / 0 CRITICAL |
| `boot_profiler.py --report` | 1841 tokens always-on — **sin cambio** |
| `git diff --check` | limpio |
| `_qa/bloque-security-backstop.py` | 17/17 PASS |

## Archivos modificados

- `.claude/hooks/quality-gate.js` (SOT)
- `hooks/quality-gate.js` (dist, sincronizado)
- `_qa/bloque-security-backstop.py` (nuevo)
- `config/test.registry.yaml` (registro del nuevo suite)

Ningún agente, dispatcher, proyecto externo, o política de seguridad
central tocada. Ninguna dependencia nueva instalada.

## Riesgos residuales

- missing-authorization/IDOR siguen sin cobertura determinística —
  documentado, no resuelto (correctamente, per el propio diseño).
- Interpolación en template literals hacia innerHTML no detectada.
- Cobertura limitada a JS/TS (mismo alcance que `quality-gate.js` ya tenía) —
  sin evidencia de gap específico en Python para justificar extender el
  alcance de archivos en esta pasada.
- El log JSONL es un artefacto nuevo sin consumidor todavía — preparado
  para un futuro Verification Router (Improvement D), no usado activamente
  aún; no genera costo operacional (solo se escribe, nadie lo lee todavía).

## Rollback

`git revert` del commit. Cambio aislado a un hook WARN-only + un archivo de
test nuevo + una entrada de registry — sin estado persistente crítico, sin
migración. El log JSONL es descartable sin efecto.

## Decisión

**KEEP** — pendiente de confirmación con CI real (ver commit/CI abajo antes
del veredicto final). Beneficio real y medido (4 categorías nuevas
detectadas con evidencia, 0 falsos positivos en el set de prueba final, 1
bug real encontrado y corregido durante el desarrollo mismo — señal de
rigor, no de fragilidad), costo bajo (una extensión angosta de tooling ya
existente, sin dependencias nuevas), riesgo bajo (WARN-only, fail-open,
reversible), sin regresión medible en ninguna otra dimensión.

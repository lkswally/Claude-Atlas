# Browser / Visual QA — End-to-End Diagnostic & Repair

**Fecha:** 2026-08-11
**Commit inicial:** `07d2b8a` (main, sync con origin)
**Sospecha inicial:** QA Visual / Browser / Playwright podría no estar funcionando.
**Resultado:** Browser funciona end-to-end con evidencia real de Chromium. Se encontró
y corrigió **un bug real y confirmado**: drift entre dos fuentes de verdad sobre el
estado de Playwright.

---

## 1. Baseline (protegido)

| Check | Resultado |
|-------|-----------|
| Repo / branch / HEAD | `Claude-Atlas` / `main` / `07d2b8a`, sync con origin |
| git status inicial | Solo cambios externos preexistentes (`lucas-rojo-web/*`), sin tocar |
| Healthcheck | HEALTHY — 24 PASS / 2 WARN / 0 FAIL |
| Quick (antes del fix) | 36/36 PASS |
| Secrets | exit 0, 0 filtrados |

Sin FAIL preexistente. Cambios externos identificados y excluidos de todo commit.

---

## 2. Mapa del provider real

```text
visual_qa
   ↓
core/capabilities/router.py :: resolve_capability("browser")
   ↓
provider: playwright (primario)  |  fallback: claude_in_chrome
   ↓
mcp__playwright__*  (navigate, snapshot, screenshot, click, type, evaluate,
                      console_messages, network_requests, resize, close)
   ↓
Chromium real (chromium-1223/1228 + headless-shell, instalado localmente)
```

**Provider real que usan los agentes: Playwright MCP**, documentado explícitamente en
`evidence-collector.md`: `browser` capability → `playwright (mcp__playwright__*)` |
fallback `claude_in_chrome`. NO se confundió con Claude in Chrome (que está
desconectado en esta sesión y solo es fallback).

**Config vs realidad — NO se confundió CONFIGURED con LIVE:**

| Capa | Estado antes | Estado real (verificado) |
|------|-------------|---------------------------|
| `.mcp.json` (CWD raíz `D:\ProyectosIA`) | 4 servers declarados (engram, context7, playwright, github) | sintácticamente válido |
| Handshake MCP | tool schemas `mcp__playwright__*` sin cargar al inicio | **resueltos correctamente** vía ToolSearch (deferred tool loading, comportamiento normal de la sesión) |
| Chromium | instalado (`chromium-1223`, `chromium-1228`, headless-shell) | **lanzó y navegó realmente** (ver §4) |
| `core/capabilities/registry.py` (fuente canónica del router) | `status="LIVE"` hardcoded desde F16 | correcto |
| `config/mcp.registry.yaml` (inventario declarativo F14) | `status: CONFIG_ONLY` | **incorrecto — bug encontrado (§5)** |

---

## 3. Disponibilidad real

```text
configured:      yes
reachable:       yes  (handshake MCP confirmado — tool schemas resueltos, navegación real ejecutada)
browser_launch:  yes  (Chromium real lanzado, título de página confirmado)
```

No se declaró PASS por la sola presencia de config — cada paso se verificó con acción real
(navegación, DOM, evaluate, screenshots en disco).

---

## 4. Root Cause del problema real

**Clasificación: CAPABILITY_ROUTING** (registry drift, no falla del browser en sí).

### Síntoma
`config/mcp.registry.yaml` (registry declarativo creado en la tarea F14 de esta misma
sesión) reportaba `playwright: CONFIG_ONLY`, y `tools/mcp_registry.py list_missing_required()`
listaba **playwright como "missing-required"** — una señal falsa que podía (y
probablemente hizo) alimentar la sospecha de que Browser/Playwright "no funciona como
corresponde", aunque el browser real funcionaba perfectamente.

### Evidencia
- `resolve_capability("browser")` (el router REAL que consultan los agentes, según
  `agent-protocol.md` y `evidence-collector.md`) devolvía `status='LIVE'` — correcto.
- `core/capabilities/registry.py` (docstring: *"Single source of truth for capability →
  MCP provider mapping"*) tenía `Provider("playwright", ..., "LIVE", ...)` hardcoded
  desde F16 — correcto y sin cambios necesarios.
- `config/mcp.registry.yaml` (F14, escrito en una sesión anterior antes de que el
  servidor Playwright MCP reconectara) seguía en `CONFIG_ONLY` — **nunca se refrescó**.
- Smoke test E2E real (§6) confirma de forma independiente que el browser funciona: dos
  fuentes de verdad coexistían y estaban en desacuerdo sobre el mismo hecho.

### Archivo/componente responsable
`config/mcp.registry.yaml` (entrada `playwright`) — desactualizado respecto a
`core/capabilities/registry.py` y respecto a la realidad de la sesión.

### Por qué no es más grave
El pipeline real de agentes (`evidence-collector`, `reality-checker`) consulta
`resolve_capability()`, **no** `mcp.registry.yaml` directamente para decidir si usar
browser — por lo que la capacidad de QA visual real de ATLAS **nunca estuvo rota**. El
bug es de **observabilidad/reporting**: un humano (o el healthcheck) leyendo
`config/mcp.registry.yaml` recibía información falsa.

---

## 5. Fix aplicado (LOW risk, confirmado)

| Archivo | Cambio |
|---------|--------|
| `config/mcp.registry.yaml` | `playwright.status`: `CONFIG_ONLY` → `LIVE`; `last_confirmed_live` actualizado a `2026-08-11`; `install_notes` documenta la confirmación E2E real; nota agregada advirtiendo del riesgo de drift entre esta YAML y `core/capabilities/registry.py`; header `updated`/`version` bump |
| `_qa/bloque-F14-mcp-registry.py` | Nuevo test **T15** — regression test que compara `mcp.registry.yaml` status vs `resolve_capability("browser")` status y falla si vuelven a desincronizarse |

**Clasificación del fix:** "registry incorrecto" — explícitamente permitido para
corrección autónoma. Cambio de un campo declarativo + un test; sin tocar dispatcher,
runtime, agentes, seguridad ni proyectos.

**Rollback:** trivial — `git revert` del commit; sin estado, sin migración.

---

## 6. Browser Smoke Test REAL — página sintética aislada

Página servida en `http://localhost:55526/index.html` (fuera de todo proyecto
registrado, `python -m http.server` en puerto libre, verificado HTTP 200 con curl antes
de tocar el browser).

| Paso | Resultado | Evidencia |
|------|-----------|-----------|
| BROWSER_LAUNCH | **PASS** | Chromium real lanzado, `Page Title: "ATLAS Browser QA Test"` |
| NAVIGATION | **PASS** | `page.goto('http://localhost:55526/index.html')` ejecutado |
| DOM_READ | **PASS** | `#atlas-test` encontrado, texto exacto "ATLAS Browser QA OK" |
| INTERACTION | **PASS** | click en `#test-button` + `browser_evaluate` confirmó `document.body.dataset.clicked === "true"` |
| SCREENSHOT | **PASS** | 3 archivos PNG reales verificados en disco (ver §evidencia) |
| CLEAN_SHUTDOWN | **PASS** | `browser_close()` → "No open tabs" |

---

## 7. Visual QA — Multi-viewport

| Viewport | Tamaño confirmado | Screenshot |
|----------|-------------------|------------|
| Desktop | 1440×900 (confirmado vía `window.innerWidth/innerHeight`) | `qa/browser-diagnostic-2026-08-11/synthetic-desktop-1440x900.png` (11,611 B) |
| Tablet | 768×1024 | `qa/browser-diagnostic-2026-08-11/synthetic-tablet-768x1024.png` (10,152 B) |
| Mobile | 390×844 | `qa/browser-diagnostic-2026-08-11/synthetic-mobile-390x844.png` (8,322 B) |

Tamaños de archivo distintos confirman renders reales y distintos (no duplicados/fabricados).

---

## 8. Console QA

| Test | Resultado |
|------|-----------|
| `console.log` detectado | **PASS** — `[LOG] ATLAS_BROWSER_TEST_READY @ index.html:14` |
| `console.error` detectado (inyectado deliberadamente) | **PASS** — `[ERROR] ATLAS_BROWSER_TEST_ERROR` capturado |
| Falso positivo descartado | El primer error observado (`favicon.ico 404`) se investigó — es comportamiento normal del browser (no hay favicon en el fixture), no un bug de la página ni de ATLAS |

---

## 9. Network QA

| Test | Resultado |
|------|-----------|
| `fetch('/atlas-test.json')` → 200 | **PASS** — `{status: 200, body: {"atlas":"ok"}}` |
| `fetch('/does-not-exist.json')` → 404 | **PASS** — confirmado por `evaluate` (`status:404, ok:false`) Y por `browser_network_requests` (`[404] File not found`), dos vías independientes |

---

## 10. JS-disabled — diagnóstico únicamente

```text
supported: no   (ninguna tool mcp__playwright__* expone toggle de JS/nuevo context con opciones)
tested:    no
```

No es un FAIL — ATLAS nunca prometió esta capacidad. No se agregó al sistema (fuera de
scope de este diagnóstico, per instrucciones explícitas de no agregar features).

---

## 11. Integración Evidence Collector

Se delegó una tarea real a un subagente (Agent tool) siguiendo el contrato de
`evidence-collector.md`, apuntando a la página sintética, con instrucción explícita de
no modificar nada.

**Resultado: PASS.** El subagente:
- Cargó `mcp__playwright__*` vía ToolSearch de forma independiente (confirmando que la
  capability es descubrible por cualquier agente, no solo por la sesión principal).
- Navegó, tomó screenshots reales (verificados con `ls`), leyó DOM, console y network.
- Devolvió un Return Envelope completo con STATUS/TAREA/ARCHIVOS/VERIFICACION/NOTAS.
- Reportó honestamente 2 hallazgos informativos sobre el comportamiento de las tools
  MCP mismas (no bugs de ATLAS — ver §12).

Cadena confirmada end-to-end:
```
Orchestrator → QA Agent (subagent) → Browser capability (resolve_capability)
→ Real browser (Chromium) → Evidence (screenshots+console+network reales)
→ Return Envelope
```

---

## 12. Hallazgos informativos (no bugs, no requieren fix)

1. **`browser_console_messages(all=true)`** mezcla mensajes de navegaciones previas del
   mismo proceso de browser. Verificado: `evidence-collector.md` **nunca instruye
   `all=true`** — el default de la tool (`all=false`, scope por navegación) ya es
   correcto. No hay bug que corregir.
2. **`browser_network_requests`** no capturó consistentemente los 404 de recursos
   fallidos (favicon) vistos en consola cuando se filtró por navegación reciente —
   comportamiento de la tool MCP externa (Microsoft Playwright MCP), no de ATLAS.
   Anotado para referencia futura, sin acción — no bloquea QA visual real.

---

## 13. Capability Router — verificación

```python
resolve_capability("browser")
# Resolution(capability='browser', provider='playwright', status='LIVE',
#            tool_prefix='mcp__playwright__',
#            fallback=Resolution(provider='claude_in_chrome', status='LIVE', ...))
```

Confirmado: una solicitud de capability `browser` resuelve correctamente a Playwright
(no a filesystem, shell genérico ni razonamiento manual). El healthcheck ya tenía un
check propio ("Capability router") que reportaba esto correctamente incluso antes del
fix — el bug estaba aislado a `config/mcp.registry.yaml` / `tools/mcp_registry.py`.

---

## 14. Prueba sobre proyecto real — LucasRojo-Web (read-only)

Condiciones respetadas: **0 archivos editados, 0 commits, 0 deploys, 0 cambios de
configuración** en el proyecto. Dependencias ya estaban instaladas (`node_modules/`
preexistente) — no se instaló nada.

| Paso | Resultado |
|------|-----------|
| Levantar servidor (`npm run dev`, Next.js 16.2.6 Turbopack) | Puerto 3000 ocupado por proceso preexistente ajeno (no tocado) → auto-fallback a 3001 |
| Primer intento de navegación | **Timeout genuino** (60s) — investigado, no oculto |
| Root cause del timeout | Log del servidor: `GET / 200 in 59s` — primer compile de Turbopack + filesystem lento (advertencia propia de Next.js), 1s más allá del timeout del cliente. Característica del proyecto, no bug de Playwright/ATLAS |
| Reintento tras compile en caliente | **PASS** — navegación en segundos |
| Título real confirmado | "Lucas Rojo — Asesoría operativa, CX y adopción de IA para pymes" |
| Desktop screenshot (1440×900) | `qa/browser-diagnostic-2026-08-11/lucas-rojo-web-desktop-1440x900.png` (1,030,281 B) |
| Mobile screenshot (390×844) | `qa/browser-diagnostic-2026-08-11/lucas-rojo-web-mobile-390x844.png` (325,576 B) |
| Console | 0 errores, 1 warning (meta tag `apple-mobile-web-app-capable` deprecado — hallazgo real del proyecto, fuera de scope, no corregido) |
| Network | 30 requests estáticos, 0 fallidos |
| Cierre | Browser cerrado, servidor dev detenido (`kill`), puerto 3001 verificado cerrado |

Esto demuestra que Browser/Visual QA funciona **no solo con la página sintética** sino
contra un proyecto Next.js real y registrado.

---

## 15. Test de regresión

`_qa/bloque-F14-mcp-registry.py::T15` — compara `config/mcp.registry.yaml`'s status de
playwright contra `core.capabilities.router.resolve_capability("browser")`. Falla si
vuelven a desincronizarse. Resultado tras el fix: **15/15 PASS** (era 14/14 antes de
agregar T15).

---

## 16. Rollback

`git revert` del commit de este diagnóstico. Sin estado persistente, sin migración, sin
dependencia nueva. El único cambio de comportamiento es que `list_missing_required()`
ya no reporta un falso positivo sobre playwright.

---

## 17. Limpieza

- Browser cerrado (2 veces — página sintética y LucasRojo-Web).
- Servidor HTTP sintético (puerto 55526) detenido — PID Windows real identificado vía
  `netstat` (el PID de bash `$!` no coincidía con el PID real del proceso).
- Servidor dev de LucasRojo-Web (puerto 3001) detenido.
- 0 procesos node/next/http.server huérfanos (verificado).
- 0 puertos abiertos por mí (verificado con `netstat`; el listener en 3000 es un
  proceso preexistente ajeno, no tocado).
- Página sintética + logs temporales eliminados del scratchpad.
- Artefactos dispersos (`D:\ProyectosIA\*.png`, `D:\ProyectosIA\.playwright-mcp\`)
  eliminados; evidencia real preservada en `qa/browser-diagnostic-2026-08-11/`
  (gitignored, sigue la convención existente de ATLAS para evidencia QA).
- `lucas-rojo-web/web` — `git status` confirmado sin cambios causados por mí.

---

## 18. Validación final de ATLAS (post-fix)

| Check | Resultado |
|-------|-----------|
| compileall | exit 0 |
| Healthcheck | HEALTHY — 24 PASS / 2 WARN / 0 FAIL |
| Quick | **36/36 PASS** (68.4s) |
| Release | **39/39 PASS** (72.6s) |
| Secrets | exit 0 |
| Claim linter | 0 HIGH / 0 CRITICAL |
| git diff --check (ATLAS) | limpio |
| Test de regresión F14 | 15/15 PASS |
| Browser E2E (repetido tras fix) | PASS en ambos escenarios (sintético + LucasRojo-Web) |

---

## Estado final

## BROWSER_FIXED

El browser/visual QA de ATLAS **funciona correctamente** con evidencia real de
Chromium (navegación, DOM, interacción, screenshots multi-viewport, console, network,
integración con evidence-collector, prueba contra proyecto real). Se encontró y
corrigió un bug real, confirmado y de bajo riesgo: `config/mcp.registry.yaml` reportaba
un falso `CONFIG_ONLY` para Playwright, desincronizado de la fuente canónica
(`core/capabilities/registry.py` vía `resolve_capability()`), lo cual podía alimentar la
sospecha original de mal funcionamiento sin que el browser estuviera realmente roto.
Fix aplicado + test de regresión agregado + validación completa en verde.

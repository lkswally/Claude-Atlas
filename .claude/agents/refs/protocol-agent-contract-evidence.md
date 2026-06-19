# Protocol Contracts — Evidence (screenshot, visual evidence, invocation tracking, anti-loop, fidelity, console, network)

> Lazy contract ref extracted from protocol-agent-contracts.md in F33. Verbatim — behavior unchanged.
> Load via the contracts index when your task involves these concerns.

## 4.15. Screenshot Hash Verification (Bloque 1J.2)

**Alcance**: cierra el último gap de evidencia visual sin verificación independiente. Verifica que la `visual_evidence` reportada por el agente tenga:
- `screenshot_path` real apuntando a archivo existente
- hash SHA256 computable y verificable
- coincidencia con hash declarado (si el agente lo provee)

Detecta agentes que reportan evidencia sin haber capturado realmente el screenshot, o que cambian el archivo entre runs.

### Helper

```python
report = dispatcher.verify_screenshot_evidence(
    evidence={"screenshot_path": "qa-evidence/task-1.png", "screenshot_hash": "abc..."},
    expected_path="qa-evidence/task-1.png",  # opcional
)
# {
#   "verdict": "ok" | "mismatch" | "unverifiable",
#   "checks": [...], "discrepancies": [...],
#   "computed_hash": str, "file_exists": bool, "file_size": int,
# }
```

### Reglas de severidad

| Caso | Severidad | Verdict |
|------|-----------|---------|
| Evidence no es dict / sin path | - | unverifiable |
| Archivo declarado NO existe | CRITICAL | mismatch (evidencia fantasma) |
| Hash declarado != computado | CRITICAL | mismatch (tampering) |
| `expected_path` provisto y difiere | HIGH | mismatch (screenshot incorrecto) |
| Archivo 0 bytes (vacío) | HIGH | mismatch (screenshot inválido) |
| Archivo < 1KB | LOW | ok (sospechoso, informativo) |
| File OK + hash OK (o no declarado) | - | ok |

### Patrón típico de uso (en evidence-collector)

```python
# 1. Capturar screenshot via Playwright
screenshot_path = "qa-evidence/task-3-screenshot.png"
mcp__playwright__browser_take_screenshot(path=screenshot_path)

# 2. Agente reporta evidence en envelope con path
envelope_evidence = {"screenshot_path": screenshot_path, ...}

# 3. Dispatcher verifica
report = dispatcher.verify_screenshot_evidence(envelope_evidence)
if report["verdict"] == "mismatch":
    # CRITICAL: no se capturo screenshot o fue tamperado
    return {"status": "FAIL", "bloqueadores": [d["details"] for d in report["discrepancies"]]}

# 4. Caller cachea el hash para futuras verificaciones
cached_hash = report["computed_hash"]
```

### Detección de tampering entre runs

Si en QA #1 se cachea hash, y en QA #2 el agente reporta el mismo path con el hash viejo pero el archivo fue modificado → CRITICAL mismatch. El verificador atrapa cambios silenciosos.

### LO QUE 1J.2 NO HACE

- ❌ NO valida que el screenshot sea de la pagina correcta — solo que exista y tenga hash verificable
- ❌ NO compara contra screenshot "esperado" a nivel de contenido (eso es 1H.3 con LLM-as-judge multimodal)
- ❌ Archivos pequeños (<1KB) se marcan LOW pero no bloquean
- ❌ `expected_path` es opcional — sin él, no se verifica que sea el screenshot correcto
- ❌ Sin path declarado → unverifiable (no detecta evidencia inventada si el agente no menciona path)

---

## 4.14. Visual Evidence Independent Verification (Bloque 1J.1)

**Alcance**: cierra el gap "honestidad supuesta del agente" sobre `design_intelligence`. El dispatcher **re-invoca el skill independientemente** y compara con lo declarado por el agente. Mismo patrón que `verify_pre_return_audit` (1A.15) pero para design intelligence.

### Helper

```python
report = dispatcher.verify_design_intelligence_real(envelope)
# {
#   "verdict": "match" | "mismatch" | "unverifiable",
#   "checks": [...], "discrepancies": [...],
#   "skill_query_result": {...},
#   "note": str,
# }
```

### Reglas de severidad

| Caso | Severidad | Verdict |
|------|-----------|---------|
| `design_intelligence` ausente / `queried=false` | - | unverifiable |
| `industry` no declarada | - | unverifiable |
| Skill no disponible | - | unverifiable (no rompe) |
| `industry` declarada NO retorna resultados del skill | CRITICAL | mismatch |
| `style` declarado NO aparece en results para esa industry | HIGH | mismatch |
| `verified_against` contiene CSV que no existe en el catalogo | LOW | match (warning) |
| Todo coincide | - | match |

### Cuándo invocar (orquestador)

Tras recibir envelope de `ux-architect` o `ui-designer` con `design_intelligence` declarada:
1. Validar formato → `validate_return_envelope(mode="design_strict")` (1C.1)
2. **Re-verificar independientemente → `verify_design_intelligence_real(envelope)` (1J.1)**
3. Si verdict=="mismatch" → re-delegar al agente con detalle de discrepancias

### Match parcial por tokens

El style declarado se compara token-by-token: si el agente dice "Glassmorphism" y el skill responde "Glassmorphism + Flat Design" → MATCH parcial OK. Esto evita falsos mismatches por nombres compuestos.

### LO QUE 1J.1 NO HACE

- ❌ NO valida que el agente realmente vio el screenshot — solo re-invoca el skill con lo declarado
- ❌ NO compara visual evidence (eso es 1H.3) — compara la declaración de `design_intelligence` contra el output real del skill
- ❌ Skill unavailable → unverifiable (no rompe pero no garantiza)
- ❌ Honestidad sobre `verified_against` es LOW (informativo, no block)
- ❌ NO detecta si el agente fue creativo combinando estilos no listados (solo si reporta uno completamente inventado)

---

## 4.13. Runtime Invocation Tracking + Enforcement (Bloque 1G.2)

**Alcance**: convierte el wiring documental de 1G.1 en wiring **medible**. Cada helper obligatorio del dispatcher registra automáticamente su invocación en `.pipeline/invocation-log.jsonl`. El orquestador puede auditar en runtime qué helpers se invocaron — diferencia operativa real vs documental.

### Cómo funciona

- Cada método obligatorio del dispatcher (12 helpers) llama `_record_invocation()` al inicio
- Log append-only en `.pipeline/invocation-log.jsonl` (atomic, fail-open)
- Cada entry: `{helper, timestamp, context, outcome, version}`

### API de audit

```python
audit = dispatcher.audit_invocations(
    required_helpers=["validate_return_envelope", "should_skip_qa", "inspect_network_requests"],
    since_seconds=300,  # ventana 5 min
    context_filter={"mode": "dev_strict"},  # opcional
)
# {
#   "verdict": "complete" | "incomplete",
#   "required": [...], "invoked": [...], "missing": [...], "extra": [...],
#   "total_invocations": N, "window_seconds": N, "note": str,
# }
```

### Helpers trackeados automaticamente (15)

`validate_return_envelope`, `verify_pre_return_audit`, `verify_declared_files`, `verify_design_intelligence`, `consult_design_intelligence`, `get_cajon_full`, `resolve_ambiguous_project`, `should_skip_qa`, `cache_qa_result`, `run_certification_re_runs`, `inspect_network_requests`, `analyze_console_messages`, `check_visual_fidelity`, `record_session_summary`, `check_cross_session_loops`.

### Cuándo auditar (orquestador)

| Momento | Required helpers esperados |
|---------|---------------------------|
| Cerrar tarea Fase 3 dev | `validate_return_envelope` (dev_strict) |
| Cerrar tarea Fase 3 QA | `validate_return_envelope` (qa_strict), `should_skip_qa`, `cache_qa_result`, `inspect_network_requests`, `analyze_console_messages` |
| Cerrar tarea Fase 2 ux/ui | `validate_return_envelope` (design_strict), `consult_design_intelligence` |
| Antes de CERTIFIED Fase 4 | `run_certification_re_runs`, `check_visual_fidelity` |
| Cierre de sesión | `record_session_summary` |

### Diferencia con 1G.1

- **1G.1** documenta en prompts (anti-regresión documental sin garantía runtime)
- **1G.2** instrumenta el código Python: si el helper fue llamado, queda registro objetivo; si no, queda evidencia

### LO QUE 1G.2 NO HACE

- ❌ NO bloquea automáticamente — el audit produce verdict que el orquestador debe consumir y actuar
- ❌ NO trackea tool calls Read/Edit/Write del agente (eso es `delegation_tracker` 1D.1)
- ❌ Requiere que el dispatcher se invoque desde Python. Si el agente no pasa por el dispatcher (salta directo a tools), no hay log
- ❌ Log crece append-only sin prune automático
- ❌ Orquestador debe consultar `audit_invocations()` — el audit es opt-in

---

## 4.12. Anti-Loop INTER-Sesion Contract (Bloque 1I.1)

**Alcance**: extiende `delegation_tracker` (1D.1) con persistencia cross-session via append-only log. Detecta loops que persisten entre sesiones — flags que se "olvidaban" al cerrar sesion ahora se acumulan.

### Helpers

```python
# Al cerrar trabajo sobre una task o al cerrar sesion:
dispatcher.record_session_summary(session_id, task_id="atlas/tarea-3")

# Antes de invocar a un subagente con esa task_id:
result = dispatcher.check_cross_session_loops(task_id, recent_sessions=3)
# {"verdict": "ok" | "loop_detected", "flags_sticky": {...}, "loop_count": {...}}
```

### Reglas de stickiness

Para cada flag (`escalation_needed`, `pause_recommended`, `fresh_review_recommended`):
- Si aparece en **>= 2 de las últimas 3 sesiones** para esa task_id → `*_sticky = True`
- Si alguna sticky → `verdict = "loop_detected"`
- Resultado: el orquestador debe **escalar inmediatamente** sin esperar nuevos triggers intra-sesión

### Persistencia

- Archivo: `{project_root}/.pipeline/delegation-history.jsonl`
- Formato: append-only JSON Lines (una entry por sesión)
- Cada entry: `{session_id, task_id, timestamp, flags, consecutive_reads, files_modified_count, ...}`
- Resiliente: lineas malformadas se saltean (fail-open en `_read_history`)
- Crece append-only — prune manual via futuro helper si se necesita

### Cuándo invocar

| Momento | Helper | Por qué |
|---------|--------|---------|
| Tras cada tarea completada en Fase 3 | `record_session_summary(session_id, task_id)` | Snapshot del estado actual para historial |
| Al cerrar sesión (en orquestador) | `record_session_summary(session_id, task_id=None)` | Snapshot final |
| Antes de re-delegar a un subagente con task_id | `check_cross_session_loops(task_id)` | Detectar si la task viene loopeando hace sesiones |
| Si verdict == "loop_detected" | Escalar al usuario | NO seguir reintentando |

### LO QUE 1I.1 NO HACE

- ❌ NO bloquea automáticamente — produce verdict que el agente/orquestador debe consumir
- ❌ NO purga history vieja — append-only, crece linealmente
- ❌ Honestidad del task_id supuesta — caller debe usar IDs consistentes entre sesiones (recomendado: `{proyecto}/tarea-{N}` o `{proyecto}/{cajon}`)
- ❌ Orquestador agente debe leer su md y consultar (capability disponible, no auto-invocada)
- ❌ NO usa Engram para persistir (decision: file local más simple para análisis local; cross-machine sync futuro)

---

## 4.11. Visual Fidelity Checker Contract (Bloque 1H.3)

**Alcance**: TERCERA capa de multi-layer QA. Compara visual spec declarada vs evidence reportada por el agente (LLM-as-judge multimodal). Cierra el set de capas QA acordado (1H.1 network + 1H.2 console + 1H.3 visual).

### Helper

```python
report = dispatcher.check_visual_fidelity(spec, evidence)
# {"verdict": "OK"|"WARN"|"FAIL", "issues": [...], "summary": {...}}
```

### Inputs esperados

**spec** (del design-system, declarada por ui-designer/ux-architect):
```python
{
  "declared_palette": {"primary": "#hex", "accent": "#hex", ...},
  "declared_typography": {"heading_font": str, "body_font": str},
  "mood_preset": "brutalist" | "minimal" | "luxury" | ...,
  "anti_patterns_obligatorios": ["no-gradient-overuse", ...],
  "layout_pattern": "hero-asymmetric" | "hero-centered" | ...,
}
```

**evidence** (el agente Claude multimodal analiza screenshot y reporta):
```python
{
  "detected_colors": ["#hex", ...],   # dominantes del screenshot
  "detected_typography": {"heading_font": str, "body_font": str},
  "detected_mood": str,
  "anti_pattern_violations": [str, ...],   # violaciones que el agente vio
  "detected_layout_pattern": str,
}
```

### Severidad y verdict

| Severidad | Casos | Verdict |
|-----------|-------|---------|
| **CRITICAL** | Primary color hex distance > tolerancia (~30 ΔE RGB), heading font family difiere, evidence sin detected_colors | **FAIL** (bloquea PASS) |
| **HIGH** | Secondary/accent color desviado, body font difiere, anti-pattern violado, mood mismatch | WARN |
| **MEDIUM** | Layout pattern divergente | OK informativo |
| **LOW** | Detalles menores | OK |

### Cómo se invoca (en evidence-collector o reality-checker)

El agente capta screenshot vía Playwright, lo analiza con su capacidad multimodal, produce evidence estructurada. El helper compara:

```python
# 1. Cargar spec del design-system desde Engram
spec = dispatcher.get_cajon_full(proyecto, f"{proyecto}/design-system")["content"]

# 2. Agente analiza screenshot multimodal y produce evidence
evidence = {
    "detected_colors": [...],  # extraidos del screenshot
    "detected_typography": {...},
    ...
}

# 3. Comparar
report = dispatcher.check_visual_fidelity(spec, evidence)

# 4. Aplicar verdict
if report["verdict"] == "FAIL":
    return {"status": "FAIL", "bloqueadores": [i["details"] for i in report["issues"]]}
```

### LO QUE 1H.3 NO HACE

- ❌ NO analiza imágenes por sí mismo — el agente Claude multimodal lo hace y reporta evidence
- ❌ NO pixel-perfect — usa tolerancias RGB (ΔE ~30 para primary, ~50 para secondary)
- ❌ NO valida microcopy, spacing exacto, icon style, ornamentos
- ❌ NO detecta jerarquía visual ni rythm — solo color/font/pattern
- ❌ Evidence-collector / reality-checker deben leer su md y consultar
- ❌ Honestidad del agente es supuesta (puede reportar evidence inventada)

---

## 4.10. Console Log Analysis Contract (Bloque 1H.2)

**Alcance**: SEGUNDA capa de multi-layer QA. SOLO cubre análisis de console messages. NO cubre network inspection (1H.1) ni visual fidelity (1H.3).

### Helper

```python
report = dispatcher.analyze_console_messages(
    messages=playwright_console_messages,
    third_party_origin_patterns=[r"analytics", r"hotjar"],  # opcional
)
# {"verdict": "OK"|"WARN"|"FAIL", "issues": [...], "summary": {...}}
```

### Patrones detectados por severidad

| Severidad | Patrones | Tipo |
|-----------|----------|------|
| **CRITICAL** | `Uncaught\|Unhandled`, `CORS\|Access-Control-Allow-Origin`, `Content Security Policy\|Refused to (load\|execute)`, `Hydration failed\|Text content does not match`, `Cannot read properties of (null\|undefined)`, `is not a function`, `ReferenceError` | uncaught_exception, cors_error, csp_violation, hydration_mismatch, null_undefined_access, etc. |
| **HIGH** | `Each child in a list should have a unique "?key"?`, `Invalid hook call\|Rules of Hooks`, `act\(\).*not wrapped`, `deprecated.*\(API\|method\)`, `memory leak\|leaked`, **`type=error` genérico** | react_missing_key, react_hooks_violation, deprecation, console_error_generic |
| **MEDIUM** | `type=warning\|warn` genérico no matcheado | console_warning_generic |
| **LOW** | `type=log\|info\|debug`, mensajes de **third-party origins**, **noise** (DevTools, source maps) | console_log, third-party degraded |

### Filtros (ignorados, no cuentan como issues)

- `Download the React DevTools for a better experience`
- `Source map (not found|missing|invalid)`
- `DevTools listening` / `chrome-extension://`
- `Google Analytics not loaded`

### Third-party degradation

Si `third_party_origin_patterns` matchea el `location.url` del mensaje, su severidad se degrada automáticamente a LOW (con flag `third_party_degraded=true`). Útil para no fallar QA por errores en tracking scripts.

### LO QUE 1H.2 NO HACE

- ❌ NO ejecuta código de los mensajes — solo analiza texto
- ❌ NO valida call stacks completos
- ❌ NO cubre visual fidelity (1H.3)
- ❌ Evidence-collector agente debe leer su md y consultar el helper

---

## 4.9. Network Inspection Contract (Bloque 1H.1)

**Alcance**: PRIMERA capa de multi-layer QA. SOLO cubre análisis de network requests capturados por Playwright. NO cubre console logs (1H.2) ni visual fidelity (1H.3).

### Helper

```python
report = dispatcher.inspect_network_requests(
    requests=playwright_network_requests,  # de browser_network_requests
    page_origin="https://app.com",         # para distinguir same-origin
)
# {"verdict": "OK" | "WARN" | "FAIL", "issues": [...], "summary": {...}, "note": str}
```

### Severidad y verdict

| Severidad | Casos | Efecto |
|-----------|-------|--------|
| **CRITICAL** | 5xx, mixed content HTTPS→HTTP, network errors (`ERR_*`) | verdict=FAIL → **bloquea QA PASS** |
| **HIGH** | 4xx en asset crítico same-origin (.js, .css, /api/), redirect chain >3 | verdict=WARN → no bloquea, reportar |
| **MEDIUM** | 4xx en same-origin no-crítico, requests >5s | verdict=OK informativo |
| **LOW** | 4xx en cross-origin (tracking), favicon missing | verdict=OK informativo |

### Cuándo invocar (en evidence-collector)

Después de cada `browser_navigate` + interacciones que disparen requests:
1. `browser_network_requests` → captura la lista
2. `dispatcher.inspect_network_requests(requests, page_origin)` → analiza
3. Si verdict=FAIL → STATUS=FAIL en el envelope QA
4. Si verdict=WARN → STATUS=PASS con WARN en NOTAS
5. Si verdict=OK → continuar normalmente

### Casos detectados que antes pasaban como QA PASS

- API endpoint propio devuelve 500 silenciosamente → ahora CRITICAL
- JS bundle 404 (cache miss en deploy roto) → ahora HIGH
- Mixed content (page HTTPS → CDN HTTP) → ahora CRITICAL
- Redirect loop (5+ redirects) → ahora HIGH
- Auth endpoint 401/403 que el agente ignoró visualmente → ahora HIGH (es /auth/)

### LO QUE 1H.1 NO HACE

- ❌ NO inspecciona response bodies — solo metadata (status, url, duration, error)
- ❌ NO valida estructura JSON de APIs
- ❌ NO mide payload size — solo duración
- ❌ NO cubre console logs (1H.2)
- ❌ NO cubre visual fidelity LLM-as-judge (1H.3)
- ❌ Evidence-collector agente debe leer su md y consultar el helper. Capability disponible, no auto-invocada por dispatcher

---


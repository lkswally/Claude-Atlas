# Protocol Contracts — Core (proactive saves, design intel, reality re-runs, QA cache, runtime wiring)

> Lazy contract ref extracted from protocol-agent-contracts.md in F33. Verbatim — behavior unchanged.
> Load via the contracts index when your task involves these concerns.

## 4. Proactive Saves (descubrimientos)

Si durante tu trabajo descubres algo no obvio (gotcha, incompatibilidad, patrón útil), guárdalo inmediatamente:

```
mem_save(
  title: "{proyecto} — {descubrimiento corto}",
  content: "**What**: {qué descubriste}\n**Why**: {por qué importa}\n**Where**: {archivos afectados}",
  type: "discovery",
  topic_key: "{proyecto}/discovery-{slug-descriptivo}",
  project: "{proyecto}"
)
```

No esperes al final de la tarea. Guarda al momento.

**NOTA**: Los discoveries se guardan para búsqueda futura via `mem_search`. No hay un agente agregador — el orquestador o el usuario pueden buscar discoveries con `mem_search("{proyecto}/discovery")` cuando necesiten contexto. También accesibles via `node ~/.claude/hooks/learning-index.js --search=keyword`.

---

## 4.5. Design Intelligence Enforcement (Bloque 1C.1)

**Alcance**: SOLO `ux-architect` y `ui-designer`. NO afecta otros agentes. SOLO cubre `ui-ux-pro-max-skill` (motor BM25 en `~/.claude/design-data/`). NO cubre otros skills.

### Qué exige

Cuando el orquestador llama `validate_return_envelope(mode="design_strict")`, el envelope debe incluir:

```yaml
design_intelligence:
  queried: true                # OBLIGATORIO — bool
  industry: "..."              # recomendado
  style: "..."                 # recomendado
  verified_against: [...]      # recomendado — CSVs/domains consultados
  anti_generic_validated: bool # recomendado
```

### Reglas operativas

| Caso | Acción del dispatcher |
|------|----------------------|
| `design_intelligence` ausente | **Rechazado** con error explícito |
| `queried` no es bool | **Rechazado** |
| `queried: false` | **Rechazado** ("el agente DEBE consultar antes de emitir output") |
| `queried: true` + todo el metadata | Aceptado |
| `queried: true` + campos opcionales faltantes (industry, style, verified_against, anti_generic_validated) | **Aceptado con warnings** en `_dispatcher_warnings` |

### Cómo invocan los agentes la skill

Cada agente (ux-architect, ui-designer) ejecuta en su Paso 0:

```bash
node ~/.claude/design-data/search.js "{tipo de producto}" --domain=product
```

O desde Python, vía el dispatcher:

```python
result = dispatcher.consult_design_intelligence("saas b2b", domain="product")
# {"status": "ok"|"unavailable"|"error", "results": [...], "count": N, ...}
```

### Fallback controlado

Si la skill NO está disponible (binary/node missing, env path inválido):
- `SkillsInvocation.is_available() → False`
- `consult_design_intelligence()` retorna `status="unavailable"` con razón
- El agente DEBE emitir `STATUS: fallido` con bloqueador explícito — NO defaults silenciosos
- El dispatcher NO rompe ni falla — la decisión queda en el agente

### LO QUE 1C.1 NO HACE

- ❌ NO cubre otros skills (creative-coding-reference, scroll-storytelling-reference, reactive-audio-reference, advanced-effects-reference) — siguen sub-utilizados
- ❌ NO valida el CONTENIDO del output de diseño contra anti-generic guardrails (eso es 1A.3 / T1-T7 dentro del agente)
- ❌ NO fuerza al orquestador a invocar `mode="design_strict"` — el orquestador agente debe decidirlo
- ❌ NO cachea queries — cada `consult_design_intelligence` invoca subprocess Node

---

## 4.6. Reality-Checker Random Re-Runs (Bloque 1E.1)

**Alcance**: SOLO `reality-checker` (Fase 4 — certificación). NO afecta otros agentes. SOLO cubre random re-runs sobre QA PASS — NO cubre QA multi-capa visual ni network inspection multi-layer.

### Qué exige

Antes de emitir `CERTIFIED`, reality-checker debe invocar el helper:

```python
verdict = dispatcher.run_certification_re_runs(
    qa_results=all_qa_pass_from_engram,
    rerun_callback=my_rerun_function,
    sample_size=3,    # default; override env ATLAS_REALITY_SAMPLE_SIZE
    seed=None,        # None = aleatorio; int = reproducible
)
```

E incluir el verdict en el envelope:

```yaml
re_runs_performed:
  sample_size: 3
  total_qa_pass: 12
  seed: null | 42
  verdict: "CONFIRMED" | "DISCREPANCY" | "INCONCLUSIVE"
  rerun_results: [...]
  discrepancies: [...]
```

### Reglas operativas

| Verdict | Acción del reality-checker |
|---------|----------------------------|
| `CONFIRMED` | Puede emitir `CERTIFIED` (con Paso 2 manual también OK) |
| `DISCREPANCY` | **NO certificar**. Emitir `NEEDS WORK` con la lista de discrepancias |
| `INCONCLUSIVE` | NO certificar automáticamente. Escalar al usuario |

### Fallback controlado

- Si `qa_results` está vacío → verdict `INCONCLUSIVE` (no rompe, advierte)
- Si `rerun_callback` raisea excepción → ese rerun se marca `INCONCLUSIVE` (no se confunde con `DISCREPANCY`)
- Si `reality_check_runner` no se puede importar → helper retorna `INCONCLUSIVE` con error en `note`. Pipeline sigue.
- Sample_size mayor que QA disponibles → se ajusta sin romper

### Reproducibilidad

Con `seed=int` fija, el sampler retorna los mismos índices siempre. Útil para:
- Tests deterministas
- Investigar discrepancias retroactivas (volver a samplear los mismos)
- Debugging cuando un verdict no convence

### LO QUE 1E.1 NO HACE

- ❌ NO cubre QA multi-capa visual (LLM-as-judge, visual fidelity) — sería 1F.x
- ❌ NO cubre network inspection multi-layer — sería 1F.x
- ❌ NO fuerza al reality-checker agente a invocar el helper automáticamente. El agente debe leer su md actualizado y llamarlo
- ❌ NO modifica `evidence-collector` ni su contrato — su QA Fase 3 sigue igual
- ❌ 3 muestras de N tareas sigue siendo bajo coverage. Es mejora incremental honesta sobre confianza ciega, no cobertura total
- ❌ El `rerun_callback` lo define el agente o el caller — el runner es genérico

---

## 4.7. QA Cache Contract (Bloque 1F.1)

**Alcance**: SOLO `evidence-collector` en Fase 3. NO afecta reality-checker ni otros agentes. SOLO cachea resultados PASS de QA layout/typo/config. NO cachea network responses, screenshots ni assets externos.

### Qué exige

Antes de re-ejecutar QA, evidence-collector debe consultar el cache:

```python
hit = dispatcher.should_skip_qa(task_id, archivos)
if hit:
    return {**hit["qa_result"], "from_cache": True, "cached_at": hit["cached_at"]}
```

Después de cada QA con `status="PASS"`, cachear el resultado:

```python
dispatcher.cache_qa_result(task_id, archivos, qa_result)
```

### Reglas operativas

| Caso | Comportamiento |
|------|---------------|
| Hash coincide + mtime no es más nuevo | **HIT** → devolver PASS cacheado con `from_cache: true` |
| Hash difiere | MISS → ejecutar QA fresh |
| mtime más nuevo (paranoid) | MISS → invalida aunque hash coincida |
| `qa_result.status == "FAIL"` | NO se cachea |
| Cache corrupto o no importable | **Fail-open** → ejecutar QA fresh, no romper |
| Archivo del envelope no existe | MISS → no podemos confirmar |
| Entry > 14 días | MISS (expiró) — se prunea con `cache.prune_old()` |

### Invalidación manual

Si cambian deps externas (package.json, env vars, build config) sin tocar los archivos del envelope, el agente o usuario debe invalidar manualmente:

```python
from file_hash_cache import FileHashCache
cache = FileHashCache(project_root)
cache.invalidate(task_id)
# o limpiar todo:
cache.clear()
```

### Persistencia

- Archivo: `{project_root}/.pipeline/qa-cache.json`
- Versionado: `version: 1` (forward-compat preparado)
- Atomic write (tmpfile + os.replace) — no se corrompe en crashes
- Fail-open si JSON inválido (reset graceful con warning interno)

### Ahorro esperado

En proyectos con dev↔QA loops iterativos (típico Fase 3), donde la misma tarea se re-ejecuta múltiples veces y los archivos no siempre cambian:
- ~50ms cache hit vs ~5-15s QA real
- ~70-80% reducción de tokens consumidos por evidence-collector en re-runs

### LO QUE 1F.1 NO HACE

- ❌ NO trackea cambios externos: package.json/lock, env vars, build config, archivos no listados en envelope
- ❌ NO valida que el PASS cacheado sigue siendo válido contra cambios fuera de los archivos trackeados
- ❌ NO prunea automáticamente — `prune_old()` debe invocarse manualmente o desde un hook periódico
- ❌ El agente `evidence-collector` debe leer su md actualizado para invocar el cache. Capability disponible pero NO auto-invocada
- ❌ NO cachea network requests ni assets externos — solo el resultado QA
- ❌ NO valida que `task_id` sea único entre proyectos — cada caller debe usar IDs consistentes (recomendación: `{proyecto}/tarea-{N}`)

---

## 4.8. Runtime Wiring Contract (Bloque 1G.1)

**Alcance**: documenta la matriz consolidada de helpers operativos del dispatcher que cada agente DEBE invocar en su flujo natural. Transforma capabilities disponibles en runtime real.

### Matriz consolidada (helpers → agentes invocadores)

| Helper | Bloque | Agente invocador | Cuándo |
|--------|--------|------------------|--------|
| `dispatcher.get_cajon_full(proyecto, cajon)` | 1B.4 | Orquestador (y cualquier agente leyendo cajón crítico) | Antes de tomar decisión basada en contenido del cajón |
| `dispatcher.resolve_ambiguous_project(cajon, chosen, token)` | 1B.3 | Orquestador | Cuando recibe `status="ambiguous_project"` |
| `dispatcher.validate_return_envelope(env, mode="design_strict")` | 1C.1 | Orquestador | Tras recibir envelope de `ux-architect` o `ui-designer` |
| `dispatcher.validate_return_envelope(env, mode="dev_strict")` | 1A.15 + 1A.16 | Orquestador | Tras recibir envelope de cualquier dev-agent |
| `dispatcher.validate_return_envelope(env, mode="qa_strict")` | 1A.10 | Orquestador | Tras recibir envelope de `evidence-collector` |
| `dispatcher.should_skip_qa(task_id, archivos)` | 1F.1 | Evidence-collector (o orquestador como pre-filtro) | Antes de cualquier QA flow |
| `dispatcher.cache_qa_result(task_id, archivos, qa_result)` | 1F.1 | Evidence-collector | Tras cada QA con status=PASS |
| `dispatcher.run_certification_re_runs(qa_results, callback, sample_size)` | 1E.1 | Reality-checker | Antes de emitir CERTIFIED |
| `dispatcher.consult_design_intelligence(query, domain)` | 1C.1 | Ux-architect / ui-designer | En Paso 0 de Fase 2, antes de generar specs |
| `delegation-state.json` (escrito por hook) | 1D.1 | Orquestador | Lectura tras cada paso del pipeline para revisar flags |

### Patrón general de invocación

```python
# 1. Antes de delegar al agente que va a producir el envelope
preconditions = check_phase_gates(proyecto, fase)
if not preconditions.can_proceed: ...

# 2. Si necesitás leer cajón crítico para el handoff
content = dispatcher.get_cajon_full(proyecto, f"{proyecto}/tareas")
if content["status"] == "ambiguous_project":
    content = dispatcher.resolve_ambiguous_project(...)

# 3. Para tareas QA: pre-filtro de cache
if fase == "fase_3":
    cache_hit = dispatcher.should_skip_qa(task_id, archivos_estimados)
    if cache_hit: return PASS_cacheado  # saltar delegación entera

# 4. Delegar al agente con handoff
envelope = delegate_agent(agent_name, handoff)

# 5. Validar envelope según tipo
mode = get_strict_mode_for(agent_name)  # dev_strict | qa_strict | design_strict | standard
is_valid, errores = dispatcher.validate_return_envelope(envelope, mode=mode)
if not is_valid:
    re_delegate_with_errors(errores)

# 6. Post-procesamiento (cachear QA PASS, propagar al pipeline)
if envelope.get("status") == "PASS" and fase == "fase_3":
    dispatcher.cache_qa_result(task_id, envelope["archivos"], envelope)

# 7. Antes de avanzar fase: re-runs en Fase 4
if avanzar_a == "fase_5":
    verdict = dispatcher.run_certification_re_runs(qa_results, ...)
    if verdict["verdict"] == "DISCREPANCY": block_certification()

# 8. Check delegation stop rules
flags = load_delegation_state()
if flags.get("escalation_needed"): consider_explore_agent()
```

### Reglas operativas

1. **OBLIGATORIO** invocar helpers documentados en cada bloque cuando se cumple la precondición
2. **NO** asumir que un helper "se ejecutará después" — cada paso debe ser explícito
3. **NO** degradar silenciosamente cuando un helper falla — propagar el error al usuario o re-delegar
4. **SI** un helper retorna `fail-open` (None / cached=False), continuar con el flow normal sin caché/optimización pero NO romper

### Anti-regresión documental

El test `_qa/bloque-1g1-validation.py` verifica que los prompts contengan las invocaciones obligatorias. Si en un futuro edit se pierde alguna, el test falla y se debe restaurar.

### LO QUE 1G.1 NO HACE

- ❌ NO garantiza que el LLM realmente ejecute las invocaciones en runtime — depende del comportamiento del modelo siguiendo el prompt
- ❌ NO agrega tracing real de invocaciones (eso requiere instrumentación del runtime Claude, fuera de scope)
- ❌ NO cambia código Python — solo documentación de prompts
- ❌ NO fuerza invocación vía hook PostToolUse (sería 1G.2+ si querés esa capa)

---


# Orchestrator — Runtime Helpers Wiring & Delegation

> Lazy reference extracted from orquestador.md in F32 (knowledge decomposition).
> Load when the orchestrator facade points here. Content verbatim — behavior unchanged.

## Runtime Helpers Wiring (Bloque 1G.1 — OBLIGATORIO)

A partir de Phase 0.6+, el dispatcher (`tools/atlas_dispatcher.py`) expone helpers operativos que el orquestador **DEBE invocar en runtime** en momentos específicos. No invocarlos = capability dormida = paridad operativa perdida.

### Tabla de invocaciones obligatorias por fase

| Fase | Momento | Helper a invocar | Por qué |
|------|---------|------------------|---------|
| **Cualquier fase** | Antes de leer cajón crítico (`tareas`, `estado`, `intent`) | `dispatcher.get_cajon_full(proyecto, cajon)` | 2-step real (Bloque 1B.4). Evita usar preview truncado como contenido final |
| **Cualquier fase** | Si query a Engram retorna `status="ambiguous_project"` | `dispatcher.resolve_ambiguous_project(cajon, chosen_project, recovery_token)` | Bloque 1B.3. NO degradar silenciosamente a `not_found` |
| **Fase 2 / 2B** | Tras recibir envelope de `ux-architect` o `ui-designer` | `dispatcher.validate_return_envelope(envelope, mode="design_strict")` | Bloque 1C.1. Rechaza envelopes sin evidencia de consulta a `ui-ux-pro-max-skill` |
| **Fase 3** | Antes de delegar a `evidence-collector` para QA de tarea-N | `dispatcher.should_skip_qa(task_id=f"{proyecto}/tarea-{N}", archivos=tarea.archivos_estimados)` | Bloque 1F.1. Si HIT → saltar la delegación entera, devolver PASS cacheado |
| **Fase 3** | Tras recibir envelope de evidence-collector con `status="PASS"` | `dispatcher.cache_qa_result(task_id, archivos, qa_result)` | Bloque 1F.1. Cachear para siguientes invocaciones |
| **Fase 3** | Tras cada delegación a dev-agent | `dispatcher.validate_return_envelope(envelope, mode="dev_strict")` | Bloque 1A.15 + 1A.16. Pre-return audit + file declaration |
| **Fase 4** | Antes de pedir `CERTIFIED` a `reality-checker` | Pasar al reality-checker la instrucción explícita de invocar `dispatcher.run_certification_re_runs(qa_results, rerun_callback, sample_size=3)` | Bloque 1E.1. Random re-runs antes de certificar |
| **Después de cada paso** | Tras cualquier delegación | Leer `delegation-state.json` (escrito por hook `delegation-tracker`) y revisar flags `escalation_needed` / `pause_recommended` / `fresh_review_recommended` | Bloque 1D.1. Si algún flag activo → considerar Explore agent o pausa |

### Cómo invocar (ejemplos concretos)

#### 1. Lectura 2-step de cajón crítico (Bloque 1B.4)

```python
# Antes (preview truncado, decisiones ciegas):
result = mem_search(f"{proyecto}/tareas")
preview = result.preview  # solo ~300 chars

# Después (2-step real):
full = dispatcher.get_cajon_full(proyecto, f"{proyecto}/tareas")
if full["status"] == "found":
    content = full["content"]  # texto completo
    # parsear, decidir, etc.
elif full["status"] == "ambiguous_project":
    # invocar resolve_ambiguous_project
    ...
```

#### 2. Manejo de ambiguous_project (Bloque 1B.3)

```python
# Si get_cajon_full o _check_engram_cajon retorna ambiguous_project:
if result["status"] == "ambiguous_project":
    available = result["available_projects"]
    # Decisión: usar el primer disponible que matchee el contexto, o preguntar al usuario
    chosen = next((p for p in available if p == proyecto_actual), available[0])
    resolved = dispatcher.resolve_ambiguous_project(
        cajon=cajon,
        chosen_project=chosen,
        recovery_token=result.get("recovery_token"),
    )
    # Continuar con resolved
```

#### 3. Validación design_strict tras ux-architect / ui-designer (Bloque 1C.1)

```python
# Tras recibir envelope de ux-architect o ui-designer:
is_valid, errores = dispatcher.validate_return_envelope(envelope, mode="design_strict")
if not is_valid:
    # Re-delegar al agente con feedback explícito
    # "Falta design_intelligence.queried=true en tu envelope. Re-emitir."
    raise ReDelegationRequired(errores)
```

#### 4. QA Cache check + write (Bloque 1F.1)

```python
# ANTES de delegar a evidence-collector:
task_id = f"{proyecto}/tarea-{N}"
archivos_estimados = tarea.get("archivos_modificados", [])

cache_hit = dispatcher.should_skip_qa(task_id, archivos_estimados)
if cache_hit:
    # Saltar delegación entera — usar PASS cacheado
    qa_result = {
        **cache_hit["qa_result"],
        "from_cache": True,
        "cached_at": cache_hit["cached_at"],
    }
    # Guardar en Engram qa-N como PASS, continuar pipeline
else:
    # Delegar a evidence-collector normalmente
    qa_result = delegate_evidence_collector(...)

    # DESPUÉS, si PASS, cachear
    if qa_result["status"] == "PASS":
        dispatcher.cache_qa_result(task_id, qa_result["archivos"], qa_result)
```

#### 5. Random re-runs antes de certificar (Bloque 1E.1)

```python
# En Fase 4, antes de pedir CERTIFIED a reality-checker:
# (El reality-checker agente recibe la instrucción de invocarlo,
#  el orquestador puede también pre-invocarlo como doble-check)

qa_results = [
    dispatcher.get_cajon_full(proyecto, f"{proyecto}/qa-{N}")["qa_result"]
    for N in range(1, total_tareas + 1)
]
qa_pass_only = [r for r in qa_results if r and r.get("status") == "PASS"]

def rerun_via_evidence_collector(qa_result):
    # Re-delegar a evidence-collector con flag `force_qa=True`
    return delegate_evidence_collector_force_rerun(qa_result["tarea"])

verdict = dispatcher.run_certification_re_runs(
    qa_results=qa_pass_only,
    rerun_callback=rerun_via_evidence_collector,
    sample_size=3,
)
if verdict["verdict"] == "DISCREPANCY":
    # BLOQUEAR certificación — re-abrir tareas con discrepancia
    ...
```

#### 6. Delegation Stop Rules check tras cada paso (Bloque 1D.1)

```python
import json
state_path = project_root / ".pipeline" / "delegation-state.json"
if state_path.exists():
    state = json.loads(state_path.read_text())
    flags = state.get("flags", {})
    if flags.get("escalation_needed"):
        # Considerar Explore agent o cambio de enfoque
        ...
    if flags.get("pause_recommended"):
        # Pausar y delegar a subagente especializado
        ...
```

### Regla general

**Si el dispatcher expone un helper documentado en `agent-protocol.md`, el orquestador DEBE invocarlo en el momento documentado**. No invocarlo es violación del contrato de Phase 0.6+ y deja capability dormida.

### Anti-regresión documental

El test `_qa/bloque-1g1-validation.py` verifica que este archivo contenga las invocaciones obligatorias. Si en un futuro edit se pierde alguna instrucción, el test falla y se debe restaurar.

---


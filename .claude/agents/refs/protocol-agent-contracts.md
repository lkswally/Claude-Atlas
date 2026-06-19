# Protocol — Per-Agent Contracts (proactive saves, design, QA cache, wiring, skills, hardening, evidence, fidelity, network, console)

> Lazy reference extracted from agent-protocol.md in F32 (knowledge decomposition).
> Load when the protocol facade points here. Content verbatim — behavior unchanged.

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

## 4.20. Skills Registry + Hard Rules (Bloque F2.1 MVP)

**Alcance**: dos capacidades **aditivas, opt-in, fail-open** que reducen la dependencia del prompt sin tocar dispatcher ni subagentes.

### 4.20.1 — Skills Registry

Catálogo declarativo en `.claude/skills.registry.yaml` con metadata buscable de las capacidades existentes en ATLAS. **No inventa skills** — indexa lo que ya existe.

**Schema por entry** (8 campos requeridos + 3 opcionales):

```yaml
- skill_id: "design.intelligence-search"     # str unico, formato "domain.name"
  domain: "design"                            # str
  agent: "ux-architect"                       # str
  description: "..."                          # str corto
  inputs: ["industry", "mood_preset"]         # list[str]
  outputs: ["anti_patterns", "style"]         # list[str]
  cost_tier: "low"                            # "low" | "medium" | "high"
  # Opcionales:
  invocation_hint: "..."
  applies_when: ["phase == fase_2"]
  reference_path: ".claude/design-data/..."
```

**API pública** (en `tools/skills_registry.py`):

```python
from skills_registry import find_skills, get_skill, list_domains, validate_registry

find_skills(domain="design")                    # lista
find_skills(agent="ui-designer")
find_skills(applies_when={"phase": "fase_2"})
find_skills(domain="design", agent="ui-designer")  # AND
get_skill("design.intelligence-search")         # dict | None
list_domains()                                  # ["branding", "design", "qa", ...]
validate_registry()                             # report dict
```

**Cuándo consultar el registry** (opcional, no forzado):

| Caso | Recomendado |
|------|-------------|
| Subagente arranca Fase X y quiere saber qué skills aplican | `find_skills(applies_when={"phase": "fase_X"})` |
| Orquestador descubre qué dominios existen | `list_domains()` |
| Validación diagnóstica del catálogo | `validate_registry()` |
| Sesión necesita verificar si una capability ya existe antes de inventar | `get_skill(...)` |

**Disable runtime**: `ATLAS_SKILLS_REGISTRY_DISABLED=1` → API retorna `[]` silenciosamente.

**Cómo agregar una skill nueva**:
1. Append una entry al `skills.registry.yaml` con los 7 campos requeridos
2. Verificar con `python tools/skills_registry.py validate`
3. NO modificar código del loader

**Lo que el registry NO hace** (explícitamente fuera de scope F2.1):
- No es motor de activación (no decide qué skill correr — solo lista)
- No tiene precondiciones evaluables (eso es Activation Contracts, diferido a F2.2)
- No tiene versionado por skill (asume v1 implícito)
- No se inyecta en subagentes (consulta es opt-in)

### 4.20.2 — Hard Rules

Reglas declarativas en `.claude/hard-rules.json` evaluadas por hook PreToolUse (`.claude/hooks/pipeline-rules.js`). Formalizan disciplina de pipeline-level que hoy vive en prosa de markdown.

**Formato JSON** (no YAML para evitar parser custom):

```json
{
  "rule_id": "no-merge-pr25-without-pilots",
  "scope": "git_merge",
  "severity": "block",
  "predicate": {"type": "command_match", "pattern": "gh\\s+pr\\s+merge\\s+25\\b"},
  "condition": {
    "type": "file_contains",
    "path": "_qa/pilotos-1L/P1.md",
    "must_contain_regex": "C3.*PASS",
    "invert": true
  },
  "message": "...",
  "bypass_env": "ATLAS_FORCE_MERGE_PR25"
}
```

**Predicate types soportados** (MVP):
- `command_match`: regex sobre el comando bash

**Condition types soportados** (MVP):
- `always`: siempre cumple si el predicate matchea
- `file_contains`: verifica que un archivo exista y contenga regex (con `invert: true` para negar)
- `file_exists`: verifica existencia (con `invert`)
- `env_var_unset`: verifica que env var NO esté seteada

**Severity**:
- `block` → exit code 2, hook ABORTA la tool call
- `warn` → exit code 0 + mensaje en stderr, tool call PROCEDE

**Reglas activas en F2.1 MVP** (4 max, regla anti-sobre-ingeniería):

1. `no-merge-pr25-without-pilots` (block) — protege PR #25 hasta C3-C7 PASS
2. `no-force-push-main` (block) — bloquea `git push --force` a main/master
3. `warn-cross-repo-commit` (warn) — detecta `cd <ruta> && git commit/push`
4. `warn-skill-registry-unused` (warn) — recordatorio de F2.1 cuando se lee prosa de agente

**Disable global**: `ATLAS_HARD_RULES_DISABLED=1` → hook es no-op total.

**Bypass per-rule**: cada regla puede declarar `bypass_env` → si esa env var = `"1"`, la regla se saltea.

**Fail-open absoluto**: cualquier error interno del hook (JSON missing, malformado, regex inválida) → exit 0 silencioso. JAMÁS bloquear por bugs propios.

**Cómo agregar una regla**:
1. Append una entry al array `rules` de `hard-rules.json`
2. Severity conservadora (`warn` por default; `block` solo en casos cristalinos)
3. Siempre incluir `bypass_env` para escape hatch documentado
4. Test con `node .claude/hooks/pipeline-rules.js` + JSON via stdin

**Lo que las hard rules NO hacen** (explícitamente fuera de scope F2.1):
- No es motor de reglas custom con expresiones lógicas AND/OR/NOT complejas
- No ejecuta código Python custom
- No tiene audit trail propio (eso es Decision Gates, diferido a F2.4)
- No reemplaza hooks existentes — es complementario
- Solo evalúa `tool_name=Bash` (otros tools pasan-through)

### 4.20.3 — Diferidos (NO entra en F2.1)

| Capa | Razón de diferimiento |
|------|------------------------|
| **Activation Contracts** (precondiciones evaluables) | Requiere DSL de evaluación. Diferido a F2.2 si Skills Registry demuestra uso |
| **Output Contracts por agente** | Mejor post-pilotos 1L. Diferido a F2.3 |
| **Decision Gates con audit trail** | Depende de Hard Rules + observabilidad. Diferido a F2.4 |
| **Token Budgets** | Requiere telemetría compleja. Diferido sin fecha |

### 4.20.5 — Usage logging + stats (Bloque F2.1.b)

Las 3 funciones públicas del registry (`find_skills`, `get_skill`, `list_domains`) registran cada invocación en `.claude/logs/skills-registry-usage.jsonl` (append-only). Archivo en `.gitignore` — runtime data, no source.

**CLI stats**:

```bash
python tools/skills_registry.py stats           # todo el log
python tools/skills_registry.py stats --since=7 # ultimos 7 dias
```

Retorna JSON: `total_invocations`, `by_event`, `top_skills`, `top_domains`, `top_agents`, `first_ts`/`last_ts`.

**Disable / override**:
- `ATLAS_SKILLS_USAGE_LOG_DISABLED=1` — no escribe (API sigue funcionando)
- `ATLAS_SKILLS_USAGE_LOG_PATH=path` — override de ubicación

**Fail-open absoluto**: cualquier error de escritura → silencioso. NUNCA interfiere con la API pública.

**Uso pretendido**: revisión a 14/30 días post-merge para decidir si el registry está siendo consultado en sesiones reales. Si `total_invocations == 0` tras 30 días → F2.1 candidato a revert.

### 4.20.6 — Hints en subagentes (Bloque F2.1.b)

Se agregó **una línea opcional** en `ux-architect.md` y `evidence-collector.md` apuntando al registry como alternativa a re-leer prosa de descubrimiento. NO modifica lógica, NO obliga — hint cognitivo opt-in. El objetivo es aumentar la probabilidad de que el agente consulte `find_skills()` cuando le ahorre tiempo, sin reescribir el subagente.

### 4.20.4 — Criterio de éxito de F2.1 (medible)

| Métrica | Target |
|---------|--------|
| Invocaciones de `find_skills()` en sesiones reales post-merge | ≥ 3 en 2 semanas |
| Hard rule `no-merge-pr25-without-pilots` activada al menos 1 vez | Sí |
| Agregar dominio nuevo (marketing, branding) requiere editar | ≤ 3 archivos |
| Tests F21-1 + F21-2 verde | 100% (27 + 16 = 43 tests) |

Si en 30 días post-merge ninguna sesión consulta el registry y ninguna hard rule se activó, **F2.1 fracasó honestamente** → candidato a revert vía rollback capa 3 (git revert).

---

## 4.19. Envelope contract formal (Bloque F1.1 reducido)

**Alcance**: formalizar la **shape** del Return Envelope con un modelo Pydantic versionado (`Envelope.v1`) sin alterar el comportamiento de `validate_return_envelope`. Capa 100% opt-in / opt-out transparente.

### Qué cambia

- El dispatcher acepta ahora **dos formas** de envelope en `validate_return_envelope(response, mode=...)`:
  - `Dict[str, Any]` (path histórico — todos los subagentes existentes)
  - Instancia de `tools.contracts.Envelope` (path nuevo — opcional, para código que quiera type-safety)
- Si el caller pasa `Envelope`, el dispatcher lo convierte a dict legacy via `to_legacy_dict()` antes de continuar.
- Si el caller pasa dict, se valida shape contra `Envelope.v1` (no-op práctico porque v1 es permisivo) y la **misma referencia** del dict continúa por el método, preservando mutaciones downstream (`_dispatcher_warnings`, `_dispatcher_enforcement`).

### Qué NO cambia

- Firma pública de `validate_return_envelope`: idéntica
- Return type: `Tuple[bool, List[str]]` idéntico
- Subagentes: ningún cambio. Siguen emitiendo dicts JSON como antes
- Hooks: ningún cambio
- Tests existentes: ninguno modificado
- Per-mode validation logic (qa_strict / dev_strict / design_strict / standard): intacta

### Importar

```python
from tools.contracts import (
    Envelope,
    EnvelopeStatus,
    EnvelopeMode,
    coerce_envelope,
    to_legacy_dict,
    ContractValidationError,
    LegacyShapeError,
)
```

### Cuándo usar dict vs Pydantic

| Caso | Recomendado |
|------|-------------|
| Subagente emite envelope desde JSON / texto | dict (sin cambios) |
| Hook PostToolUse parsea respuesta | dict (sin cambios) |
| Test existente | dict (no modificar) |
| Código nuevo de Python que construye envelope programáticamente | `Envelope` (type-safety, IDE autocomplete) |
| Necesitás validar shape antes de pasar al dispatcher | `coerce_envelope(...)` |
| Necesitás re-serializar Pydantic a dict | `to_legacy_dict(envelope)` |

### Versionado

- `Envelope.contract_version: Literal["envelope.v1"] = "envelope.v1"` (default).
- Cualquier campo nuevo que se agregue en v1 **debe** ser `Optional` con `default=None`. Sin breaking change.
- Cuando llegue v2 (futuro), se crea `Envelope.v2` aparte. v1 permanece. Coerción decide qué versión usar via `contract_version`.

### Fail-open y disable runtime

- Si `tools/contracts/` no está disponible (directorio borrado, Pydantic ausente): el dispatcher detecta `ImportError` y cae al path dict puro **sin error**.
- Env var `ATLAS_PYDANTIC_CONTRACTS_DISABLED=1`: fuerza el path dict legacy aun con contracts instalado. Útil para rollback rápido sin tocar código.

### Cobertura de tests

- `_qa/bloque-F11-1-envelope-contract.py` — 31 tests: shape, version, enums, coercion bidireccional, roundtrip, campos 1L preparados (`design_intelligence`, `references`, `editorial_compliance`, `agent`)
- `_qa/bloque-F11-5-backward-compat.py` — 24 tests: paridad observable entre path contracts vs path disabled, en los 4 modos del dispatcher

### Lo que NO incluye F1.1 reducido

- `PhaseGate.v1` — diferido a F1.1.b si se necesita
- `AuditTrail.v1` — diferido a F1.1.c
- `ClaimAudit.v1` — diferido a F1.1.d
- Refactor de `verify_*` helpers a Pydantic — no es necesario, siguen usando dict
- Migración masiva de tests existentes — explícitamente fuera de scope

## 4.18. Design Criterion Hardening (Bloques 1L.1 → 1L.4)

**Alcance**: bloque consolidado de 4 sub-bloques que endurece la barra de calidad visual en el pipeline. Cierra los gaps A.1 (especialización), A.2 (routing), A.3 (referencias planas) del diagnóstico de fase 0.6.

### 4.18.1 — Intent Classifier (1L.1)

`dispatcher.classify_user_intent(prompt)` clasifica el pedido del usuario en 4 buckets antes de delegar a project-manager-senior:

- `audit` — solo análisis, sin tocar código
- `redesign` — Fase 2 + 3 completas
- `implement` — solo Fase 3 sobre diseño existente
- `validate` — solo evidence-collector + reality-checker

Confidence `high|medium|low`. En `low` el orquestador DEBE escalar al usuario con `escalation_question`, NO decidir solo.

Rollback: `ATLAS_INTENT_CLASSIFIER_DISABLED=1`.

### 4.18.2 — design_quality bloqueante (1L.2)

En `mode="design_strict"`, `validate_return_envelope` ejecuta `design_quality_enforcement` sobre los archivos declarados. **HIGH findings rechazan el envelope** con error accionable (file:line + suggestion).

Whitelist anti-disguise por `brand.style`: solo fonts canónicas en `{brutalism, editorial-raw, neo-grotesque}` se degradan. Colors / layouts / opacity / radius **nunca** se whitelistan.

Solo extensiones UI relevantes se escanean (`.css .scss .tsx .jsx .ts .js .vue .svelte .html .astro`).

Rollback: `enforce_design_quality=False` (param) o `ATLAS_DESIGN_QUALITY_BLOCKING_DISABLED=1` (env).

### 4.18.3 — reference-driven-design obligatorio (1L.3)

`brand.references` es obligatorio en `design_strict`:
- 2 ≤ len(references) ≤ 5
- cada entry: `url` (con `.` o `://`), `rationale` ≥ 10 chars, `take` lista no-vacía, `skip` opcional lista

ui-designer (detectado por heurística) DEBE incluir `references_used: [url]`:
- list[str] no-vacía
- subset estricto de `brand.references[].url`

NO se valida URL viva (sin HTTP en runtime).

Resolución de `references`: `response.brand.references` → `response.references` → `{root}/brand.json` → `{root}/.pipeline/brand.json`.

Rollback: `enforce_references=False` (param) o `ATLAS_REFERENCES_ENFORCEMENT_DISABLED=1` (env).

### 4.18.4 — Refuerzo editorial obligatorio (1L.4)

En `design_strict` para ui-designer, el envelope DEBE incluir `editorial_compliance`:

```yaml
editorial_compliance:
  asymmetric_section: {present: bool, where: str, rationale: str (>=20 chars)}
  typography_mix: {display: str, body: str, justified: bool=true}
  references_cited: [url]              # subset estricto de references_used
  boilerplate_avoided: {explained: str (>=20 chars)}
  whitespace_intentional: {documented: bool=true}
```

Reglas duras:
- 5 sub-campos obligatorios
- `typography_mix.display.lower() != typography_mix.body.lower()` (anti-monotypo)
- `rationale` / `explained` ≥ 20 chars (anti-teatro)
- `references_cited` subset estricto de `references_used`
- `justified` y `documented` deben ser `true`

Rollback: `enforce_editorial_compliance=False` (param) o `ATLAS_EDITORIAL_ENFORCEMENT_DISABLED=1` (env).

### 4.18.5 — Cascada de validación en design_strict

Orden de checks en `validate_return_envelope(mode="design_strict")`:

```
1. STATUS valido (completado | fallido)
2. archivos / bloqueadores tipados
3. design_intelligence consultado (Bloque 1C.1)
4. design_quality_enforcement (1L.2)
5. references schema + references_used subset (1L.3)
6. editorial_compliance schema (1L.4, solo ui-designer)
7. Hard enforcement de helpers (1K.3 / 1K.4 si aplica)
```

Todos los modos NO-design_strict mantienen backward compat estricta. Ningún sub-bloque 1L se activa automáticamente fuera de `design_strict`.

### 4.18.6 — Helpers públicos agregados

- `classify_user_intent(prompt, context=None) → dict`
- `verify_design_quality(response) → (errores, warnings)`
- `verify_references(response) → (errores, warnings)`
- `verify_editorial_compliance(response) → (errores, warnings)`

Más helpers internos: `_resolve_brand_style`, `_resolve_brand_references`, `_looks_like_ui_designer`.

---

## 4.17. Auto-Invocation of Missing Helpers (Bloque 1K.4)

**Alcance**: cierra el último gap operativo de enforcement. Cuando `validate_return_envelope(enforce_helpers=True, try_auto_invoke=True)` detecta helpers faltantes en un agente crítico, el dispatcher **intenta invocar los helpers automáticamente** usando contexto inferible del envelope **antes de rechazar**.

**Diferencia con 1K.3**:
- 1K.3: missing helpers → REJECT directo, requiere re-delegación
- 1K.4: missing helpers → intenta auto-invocar con contexto del envelope → si resuelve, ACCEPT; si no, REJECT con detalle

### API

```python
is_valid, errores = dispatcher.validate_return_envelope(
    envelope,
    mode="qa_strict",
    enforce_helpers=True,
    agent_name="evidence-collector",
    try_auto_invoke=True,   # NUEVO opt-in (1K.4)
)
```

### Tabla de helpers auto-invocables

| Helper | Auto-invocable | Args inferidos del envelope |
|--------|----------------|-----------------------------|
| `should_skip_qa` | ✅ | `task_id=envelope.tarea`, `archivos=envelope.archivos` |
| `cache_qa_result` | ✅ (solo si `status=PASS`) | `task_id`, `archivos`, `qa_result=envelope` |
| `verify_screenshot_evidence` | ✅ | `evidence` con `screenshot_path` de envelope o sub-dicts (evidence/visual_evidence) |
| `verify_design_intelligence` | ✅ | `envelope` completo (lee `design_intelligence`) |
| `verify_design_intelligence_real` | ✅ | `envelope` completo |
| `consult_design_intelligence` | ✅ | `query=envelope.design_intelligence.industry`, `domain="product"` |
| `inspect_network_requests` | ❌ | Requiere lista de requests, no inferible |
| `analyze_console_messages` | ❌ | Requiere lista de messages, no inferible |
| `check_visual_fidelity` | ❌ | Requiere spec + evidence detallados |
| `run_certification_re_runs` | ❌ | Requiere qa_results + rerun_callback |
| `validate_return_envelope` | ❌ | Loop guard (auto-referente) |
| `verify_pre_return_audit` | ❌ | Requiere campo `pre_return_audit` |
| `verify_declared_files` | ❌ | Requiere git diff context |

### Salida en envelope tras auto-invoke

```python
envelope["_dispatcher_enforcement"] = {
    "verdict": "auto_fixed" | "incomplete",
    "agent_name": "evidence-collector",
    "is_critical": True,
    "missing_helpers": [...],   # still_missing (vacío si todos resueltos)
    "severity": "RESOLVED" | "HARD_BLOCK",
    "auto_invoked": [
        {"helper": "should_skip_qa", "outcome": "ok", "args_inferred": {...}},
    ],
    "auto_invoke_failed": [
        {"helper": "verify_design_intelligence_real", "reason": "..."},
    ],
    "not_auto_invocable": ["inspect_network_requests", ...],
    "audit": {...},
}
```

### Reglas operativas

1. **No inventa datos**: si el contexto requerido no está en el envelope, el helper se registra en `auto_invoke_failed` con `reason` explícita, queda en `still_missing`.
2. **Loop guard**: `validate_return_envelope` está en `NON_AUTO_INVOCABLE_HELPERS` para prevenir recursión.
3. **Honestidad sobre verdict del helper**: si auto-invoke ejecuta y el helper retorna `mismatch` o `unverifiable`, NO se cuenta como éxito silencioso — el verdict del helper queda en `auto_invoked.verdict`.
4. **`cache_qa_result` solo si PASS**: no cachea FAILs por error.
5. **`try_auto_invoke=False` (default)**: comportamiento 1K.3 puro, backward compat estricto.

### LO QUE 1K.4 NO HACE

- ❌ NO inventa datos. Si el contexto no está, no ejecuta.
- ❌ NO obliga al orquestador a usar `try_auto_invoke=True` (opt-in)
- ❌ NO cubre helpers no auto-invocables (network, console, visual_fidelity, re_runs) — siguen requiriendo re-delegación
- ❌ NO modifica el envelope salvo agregar `_dispatcher_enforcement` con detalle
- ❌ NO genera retry automático del subagent — solo intenta resolver via dispatcher
- ❌ Backward compat: `try_auto_invoke=False` (default) → 1K.3 puro

---

## 4.16. Hard Enforcement Escalation (Bloque 1K.3)

**Alcance**: cierra el gap "audit advisory pero el agente puede ignorarlo". Convierte la auditoría de invocaciones (1G.2 + 1K.1 advisory) en **rechazo activo de envelope** para agentes críticos cuando faltan helpers obligatorios.

**Diferencia con 1K.1**:
- 1K.1: hook PostToolUse emite WARN en stderr (advisory, agente puede ignorar)
- 1K.3: `validate_return_envelope(enforce_helpers=True, agent_name=...)` retorna `is_valid=False` con error explícito + marca el envelope con `_dispatcher_enforcement`

### Agentes críticos (CRITICAL_AGENTS)

`ATLASDispatcher.CRITICAL_AGENTS` set hardcoded:
- `evidence-collector` (QA Fase 3)
- `reality-checker` (Certificación Fase 4)
- `ux-architect` (Design Fase 2)
- `ui-designer` (Design Fase 2)

### API

```python
# Backward compat (default):
is_valid, errores = dispatcher.validate_return_envelope(envelope, mode="qa_strict")
# Comportamiento idéntico a pre-1K.3

# Hard Enforcement (opt-in):
is_valid, errores = dispatcher.validate_return_envelope(
    envelope,
    mode="qa_strict",
    enforce_helpers=True,
    agent_name="evidence-collector",
)
# Si evidence-collector NO invocó helpers obligatorios:
#   is_valid=False
#   envelope["_dispatcher_enforcement"] = {
#     "verdict": "incomplete", "is_critical": True,
#     "missing_helpers": [...], "severity": "HARD_BLOCK",
#     "audit": {required_for_agent, invoked, missing, ...},
#   }
```

### Matriz de comportamiento

| enforce_helpers | agent_name | Resultado |
|----------------|------------|-----------|
| False (default) | Cualquiera | Backward compat pre-1K.3 |
| True | None | Sin enforcement (no aplicable) |
| True | NO en CRITICAL_AGENTS | Skipped, validación normal |
| True | En CRITICAL_AGENTS + helpers OK | ACCEPT |
| True | En CRITICAL_AGENTS + helpers faltantes | **REJECT** + envelope marcado |

### Helper directo

```python
result = dispatcher.enforce_helpers_for_agent(envelope, agent_name="reality-checker")
# {"verdict": "passed"|"incomplete"|"skipped", "is_critical": bool,
#  "missing_helpers": [...], "severity": "HARD_BLOCK"|None}
```

### LO QUE 1K.3 NO HACE

- ❌ NO ejecuta helpers faltantes automáticamente — solo bloquea aceptación
- ❌ NO obliga al orquestador a usar `enforce_helpers=True` (opt-in)
- ❌ NO cubre agentes fuera de CRITICAL_AGENTS
- ❌ NO genera retry automático — solo señala "envelope no aceptable"
- ❌ NO modifica `qa-auto-audit.js` hook (sigue advisory, complementa)
- ❌ Honestidad de `agent_name` supuesta — caller debe pasar nombre correcto

---

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


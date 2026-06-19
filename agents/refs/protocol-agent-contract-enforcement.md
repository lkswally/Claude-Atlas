# Protocol Contracts — Enforcement (skills/hard-rules, envelope, design hardening, auto-invoke, escalation)

> Lazy contract ref extracted from protocol-agent-contracts.md in F33. Verbatim — behavior unchanged.
> Load via the contracts index when your task involves these concerns.

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


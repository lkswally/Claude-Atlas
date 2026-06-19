# Protocol — Capability Router, Metrics & Policy Engine (F16/F18/F19)

> Lazy reference extracted from agent-protocol.md in F32 (knowledge decomposition).
> Load when the protocol facade points here. Content verbatim — behavior unchanged.

## F16. Capability Router — Protocolo de solicitud de providers

> **Bloque F16** — A partir de esta versión, los agentes NO hardcodean MCPs concretos. En su lugar, solicitan capabilities por nombre. El router resuelve qué provider usar.

### Regla fundamental

```
INCORRECTO: "usar Context7 para buscar docs de React"
CORRECTO:   "solicitar capability documentation para buscar docs de React"

INCORRECTO: "llamar mcp__engram__mem_save"
CORRECTO:   "solicitar capability memory para guardar observación"

INCORRECTO: "usar Playwright para navegar"
CORRECTO:   "solicitar capability browser para navegar a URL"
```

### API de resolución (para agentes que ejecutan Python)

```python
from core.capabilities import resolve_capability

# Resolver un provider
r = resolve_capability("documentation")
# r.provider     → "context7"
# r.status       → "LIVE" | "CONFIG_ONLY" | "PENDING_TOKEN" | ...
# r.tool_prefix  → "mcp__context7__"
# r.fallback     → Resolution del siguiente provider disponible
# r.action       → "use" | "restart_session" | "set_token" | ...
# r.is_usable    → True si LIVE o CONFIG_ONLY

# Resolver múltiples capabilities
from core.capabilities import CapabilityRouter
rt = CapabilityRouter()
results = rt.resolve_many(["memory", "browser", "documentation"])
```

### Tabla de capabilities → providers

| Capability | Provider primario | Status esperado |
|---|---|---|
| `memory` | engram | LIVE |
| `documentation` | context7 | LIVE (MCP activo) |
| `browser` | playwright | LIVE (MCP activo) |
| `project_management` | notion | LIVE |
| `repository` | github | PENDING_TOKEN (necesita GITHUB_TOKEN) |
| `deployment` | vercel | PENDING_TOKEN (necesita VERCEL_TOKEN) |
| `design` | magic_21st | DEFERRED_PAID |
| `visualization` | visualize | LIVE |
| `scheduling` | scheduled_tasks | LIVE |
| `computer_control` | computer_use | LIVE |

### Capabilities críticas (nunca deben quedar sin provider)

Las capabilities `memory`, `browser`, y `documentation` son críticas. Si alguna retorna `UNAVAILABLE`, el agente debe:

1. Reportar en Return Envelope: `BLOQUEADORES: [capability {name}=UNAVAILABLE]`
2. No continuar con fallback silencioso
3. Escalar al orquestador

### Qué hacer según status

| Status | Acción |
|---|---|
| `LIVE` | Usar directamente los tools `mcp__{tool_prefix}__*` |
| `CONFIG_ONLY` | Informar al usuario que se necesita reiniciar la sesión |
| `PENDING_TOKEN` | Informar qué variable de entorno falta (ver `config/mcp.registry.yaml`) |
| `DEFERRED_PAID` | Reportar como no disponible, no intentar usar |
| `UNAVAILABLE` | Escalar como bloqueador |

## F18. Capability Runtime Metrics — Observabilidad de resoluciones

> **Bloque F18** — Cada llamada a `resolve_capability()` emite automáticamente un evento al log de observabilidad. Los agentes no necesitan hacer nada extra; el sistema es transparente.

### Log de eventos

Los eventos se escriben en `.pipeline/capability-events.jsonl` (append-only, un JSON por línea).

Campos de cada evento:
- `timestamp` — ISO-8601 UTC
- `capability` — nombre solicitado ("browser", "memory", etc.)
- `requested_by` — agente o módulo solicitante
- `provider_selected` — mcp_id del provider elegido
- `provider_status` — LIVE | CONFIG_ONLY | PENDING_TOKEN | DEFERRED_PAID | UNAVAILABLE
- `fallback_used` — true si el primario no era LIVE
- `resolution_ok` — true si el resultado es usable
- `action` — hint: "use" | "restart_session" | "set_token" | "acquire_license" | "register_provider"

### Variables de control

| Variable | Efecto |
|---|---|
| `ATLAS_CAPABILITY_EVENTS_DISABLED=1` | Desactiva el log de eventos (emit() retorna False) |
| `ATLAS_CAPABILITIES_DISABLED=1` | Desactiva el router completo (F16) |

### Metrics reader

```bash
# Resumen completo
python tools/capability_metrics.py

# Solo estado crítico
python tools/capability_metrics.py --critical

# Últimos N eventos
python tools/capability_metrics.py --last 20

# Filtrar por capability
python tools/capability_metrics.py --capability browser

# Salida machine-readable
python tools/capability_metrics.py --json
```

Exit codes del metrics reader: `0` = sano, `1` = crítica degradada, `2` = sin eventos aún.

## F19. Capability Policy Engine — Cuándo actuar, degradar o bloquear

> **Bloque F19** — El router (F16) resuelve *qué provider existe*. La policy engine (F19) decide *si está permitido usarlo*. Los agentes deben escalar o detenerse según la decisión recibida.

### Router vs. Policy: diferencia clave

| Capa | Pregunta | Respuesta |
|---|---|---|
| Router (F16) | ¿Qué provider hay disponible? | Resolution con status LIVE / CONFIG_ONLY / UNAVAILABLE |
| Policy (F19) | ¿Está permitido proceder con ese resultado? | ALLOW / WARN / DEGRADED / BLOCK |

### API de evaluación

```python
from core.capabilities.policy import evaluate_capability
from core.capabilities.router import resolve_with_policy

# Solo policy
decision = evaluate_capability("memory")
# PolicyDecision(decision="ALLOW", provider="engram", status="LIVE", ...)

# Router + policy en un solo call
resolution, decision = resolve_with_policy("browser")
```

### Tabla de decisiones para agentes

| Decision | Significado | Acción del agente |
|---|---|---|
| `ALLOW` | Provider LIVE y cumple policy | Proceder normalmente |
| `WARN` | Provider disponible pero degradado | Continuar; loguear advertencia |
| `DEGRADED` | Fallback activo, funcionalidad parcial | Continuar con cautela; informar al usuario |
| `BLOCK` | Sin provider usable y policy crítica | **Detener tarea**; informar al orquestador |
| `MISSING_POLICY` | Capability sin política declarada | Tratar como WARN; no bloquear |

### Cuándo un agente debe detenerse

Un agente **debe detenerse y escalar** cuando:
1. `decision.is_blocking is True` (BLOCK)
2. La capability es crítica para la tarea actual (no opcional)
3. El `recovery_hint` está disponible — incluirlo en el escalado

```python
if decision.is_blocking:
    raise CapabilityBlockedError(
        f"Capability '{decision.capability}' bloqueada: {decision.recovery_hint}"
    )
```

### Cuándo un agente puede degradar

Un agente puede continuar con funcionalidad reducida cuando:
- `decision.decision == "DEGRADED"` — informar al usuario del proveedor alternativo
- `decision.decision == "WARN"` — continuar, agregar nota en el output

### Cuándo pedir intervención humana

- Cualquier capability con `severity=CRITICAL` y decision != ALLOW
- BLOCK en capabilities requeridas por la tarea
- Múltiples capabilities en WARN al mismo tiempo (degradación sistémica)

### Variables de control

| Variable | Efecto |
|---|---|
| `ATLAS_CAPABILITY_POLICY_DISABLED=1` | Desactiva policy engine; todas las capabilities retornan ALLOW |
| `ATLAS_CAPABILITIES_DISABLED=1` | Desactiva router completo (F16) |
| `ATLAS_CAPABILITY_EVENTS_DISABLED=1` | Desactiva log de eventos (F18) |

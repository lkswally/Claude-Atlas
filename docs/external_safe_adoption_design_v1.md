# External Safe Adoption Design v1 — Deterministic Next Transition

**Fecha:** 2026-08-24
**Fuente del patrón:** Gentle AI v2.5.0 (`Gentleman-Programming/gentle-ai`, MIT), Receipt-Driven
Development — `next_transition.execute(review.status)`: *"the orchestrator runs what the
provider returned; it never reconstructs selectors from prose."* Corroborado por el patrón
independiente de `openclaude` (provider abstraction, sin recurso concreto adoptado — solo
señal de que "un único siguiente-paso ejecutable" es un patrón maduro en más de un proyecto).
**Candidato seleccionado tras FASE 1-6.** Ver `docs/external_architecture_radar_v1.md` para
la matriz completa y por qué el resto de los candidatos quedó en WATCH/REJECT/NO_CHANGE.

---

## 1. Candidato seleccionado

**Deterministic Next Transition** (Fase 5.B del pedido) — adaptado, no copiado. No se leyó
ni reprodujo código de gentle-ai; el diseño de abajo es una implementación independiente
sobre el mecanismo YA existente de ATLAS (`delegation_tracker.py`, Bloque 1D.1).

## 2. Gap real (confirmado en código, no supuesto)

`docs/atlas-*` y `.claude/agents/refs/orchestrator-delegation.md` §6 documentan hoy:

```python
if flags.get("escalation_needed"):
    # Considerar Explore agent o cambio de enfoque
    ...
if flags.get("pause_recommended"):
    # Pausar y delegar a subagente especializado
    ...
```

Verificado en `tools/delegation_tracker.py`: `escalation_needed`, `pause_recommended` y
`fresh_review_recommended` son **tres booleans independientes** (2³ = 8 combinaciones
posibles), cada uno con un comentario `# ...` como única guía de acción. No existe un
campo único que le diga al orquestador **qué hacer a continuación** — la decisión queda
en manos de la interpretación del orquestador en cada sesión, lo cual es exactamente
el anti-patrón que Fase 5.B pide eliminar ("no permitir múltiples next states ambiguos").

## 3. Por qué no es duplicado ni over-engineering

- No reemplaza `validate_return_envelope()`, `atlas_dispatcher.py`, ni el estado de fase
  del dispatcher — esos ya tienen sus propios gates y no se tocan.
- No introduce un sexto sistema de estado: se **deriva** de los flags que ya existen,
  no agrega nuevos triggers ni thresholds.
- Alcance restringido a los 3 flags de delegation-state — **no** intenta unificar todos
  los "próximo paso" del sistema (QA verdicts, git/deployer confirmation, phase gates)
  en una sola función. Eso sería scope creep de una sola mejora — cada uno de esos ya
  tiene su propio mecanismo de gate y queda fuera de esta adopción.

## 4. Diseño

Nueva función pura en `tools/delegation_tracker.py`, co-ubicada con el productor de los
flags (reutiliza tooling existente, no crea subsistema nuevo):

```python
NextTransition = Literal["CONTINUE", "RETRY_WITH_NEW_EVIDENCE", "BLOCK"]

def derive_next_transition(flags: dict) -> str:
    """
    Deriva un único next-step determinístico a partir de delegation-state flags.
    Precedencia (más a menos severo): pause_recommended > escalation_needed
    o fresh_review_recommended > (ninguno) CONTINUE.
    Pura función de flags -> string. Sin side effects, sin I/O.
    Advisory only — no cambia el enforcement del dispatcher.
    """
    if flags.get("pause_recommended"):
        return "BLOCK"
    if flags.get("escalation_needed") or flags.get("fresh_review_recommended"):
        return "RETRY_WITH_NEW_EVIDENCE"
    return "CONTINUE"
```

Escrita en `_save_state()` (único choke-point de escritura del state — todo call site que
mute flags pasa por ahí), como campo nuevo `next_transition` **junto a** (no en reemplazo
de) `flags`, que se preserva sin cambios para compatibilidad y detalle.

Subconjunto del enum de 6 estados que pide Fase 5.B (`CONTINUE | RETRY_WITH_NEW_EVIDENCE |
BLOCK | HUMAN_APPROVAL | ROLLBACK | COMPLETE`): este productor solo puede emitir 3 de los
6 — `HUMAN_APPROVAL` (ya cubierto por la confirmación git/deployer existente),
`ROLLBACK` y `COMPLETE` (conceptos de fase/dispatcher, no de delegation-state) quedan
explícitamente fuera de esta adopción — no se fuerza una correspondencia falsa.

## 5. Contrato

**Input:** `flags: dict` — el dict `{"escalation_needed": bool, "pause_recommended": bool,
"fresh_review_recommended": bool}` ya producido por `DelegationTracker`.

**Output:** `str`, uno de exactamente `{"CONTINUE", "RETRY_WITH_NEW_EVIDENCE", "BLOCK"}`.
Nunca `None`, nunca una lista, nunca un string fuera del set.

**Invariantes:**
- Determinístico: mismos flags → mismo output, siempre (sin estado oculto, sin I/O).
- Exactamente un valor — nunca ambiguo, nunca dos transiciones simultáneas.
- Monótono en severidad: agregar un flag activo nunca puede *bajar* la severidad del
  resultado (agregar `pause_recommended` a cualquier combinación siempre da `BLOCK`).
- Backward-compatible: `flags` sigue existiendo sin cambios; código que lo lee
  directamente (sin usar `next_transition`) sigue funcionando exactamente igual.

**Failure modes:**
- `flags` faltante/`None`/corrupto → `.get()` con default `False` en cada clave → cae a
  `CONTINUE` (fail-open, coherente con el resto de ATLAS).
- No hay excepciones posibles — función pura sobre un dict, sin try/except necesario.

**Security boundaries:** ninguna — no toca secretos, no ejecuta comandos, no llama MCPs,
no escribe fuera de `.pipeline/delegation-state.json` (ubicación ya usada por el sistema).

## 6. Impacto

| Dimensión | Impacto |
|-----------|---------|
| Tokens | +1 campo string corto por escritura de state; negligible (<10 tokens) |
| Contexto/boot | 0 — no toca CLAUDE.md, no toca ningún ref always-on |
| Runtime | 0 comportamiento nuevo forzado — el dispatcher NO lee ni enforce este campo; es un dato adicional que el orquestador PUEDE consultar, reemplazando el `# ...` ambiguo del doc por una regla concreta |
| Model routing | Ninguno |
| Agentes | 0 nuevos, 0 modificados en su prompt/contrato — solo se actualiza la doc de referencia `orchestrator-delegation.md` §6 con el ejemplo concreto |
| Seguridad | Ninguno — advisory-only |
| Dependencias | 0 nuevas |

## 7. Tests (antes de implementar)

Extender `_qa/bloque-1d1-validation.py` (test file existente del bloque 1D.1) con
`test_11_deterministic_next_transition`:
1. Sin flags activos → `CONTINUE`
2. Solo `fresh_review_recommended` → `RETRY_WITH_NEW_EVIDENCE`
3. Solo `escalation_needed` → `RETRY_WITH_NEW_EVIDENCE`
4. Solo `pause_recommended` → `BLOCK`
5. `escalation_needed` + `fresh_review_recommended` (sin pause) → `RETRY_WITH_NEW_EVIDENCE` (un solo valor, no lista)
6. `pause_recommended` + `escalation_needed` → `BLOCK` (precedencia correcta)
7. Los 3 activos → `BLOCK` (máxima severidad gana)
8. `derive_next_transition({})` (dict vacío) → `CONTINUE` (fail-open)
9. Integración real: tras `record_tool_call()` que dispare `pause_recommended`,
   `get_state()["next_transition"] == "BLOCK"` (verifica el wiring en `_save_state`, no
   solo la función aislada)
10. `flags` original sigue presente e intacto en el state (no regresión de compat)

## 8. Rollback

`git revert` del commit. La función es aislada (no la llama nadie más todavía salvo el
propio test); el campo `next_transition` es aditivo en el JSON persistido — un consumer
viejo que ignora campos desconocidos no se rompe. Sin migración de datos necesaria (el
campo se recalcula en cada `_save_state()`, no requiere backfill de archivos existentes).

## 9. Criterio KEEP / REVERT (post-implementación)

KEEP solo si: tests nuevos PASS, suite `_qa/bloque-1d1-validation.py` completa PASS,
`run_all --quick` sin regresión, `run_all --release` sin regresión, healthcheck sin FAIL,
claim linter 0 HIGH/CRITICAL nuevo, `git diff --check` limpio, sin aumento de boot tokens.
Si cualquiera de estos falla → REVERT, no implementación parcial.

# ATLAS — Operating Model

> Manual canónico de operación. Lectura obligatoria antes de invocar ATLAS sobre cualquier proyecto.
> Complementa `~/CLAUDE.md`. En caso de conflicto, este documento manda.

---

## 1. Qué es ATLAS

Sistema operativo de trabajo basado en **1 orquestador + 24 subagentes + 13 referencias técnicas** sobre Claude. Memoria persistente vía Engram. Pipeline de 5 fases. 13 hooks reactivos. Allowlist explícita.

Base estable: ver `~/CLAUDE.md` (instrucciones globales) y `~/.claude/agents/orquestador.md` (regla de oro: el orquestador NUNCA hace trabajo real inline).

---

## 2. Cuándo usar ATLAS y cuándo NO (Modo rápido / fuera de ATLAS)

### ✅ Usar ATLAS
- Proyectos completos (web, app, juego, API, full-stack).
- Modificaciones estructurales (refactors, cambios de arquitectura, migraciones).
- Diagnósticos formales sobre un proyecto existente.
- Cualquier trabajo que abarque > 1 sesión o > 3 archivos.

### ❌ NO usar ATLAS — operar en **Modo Rápido / fuera de ATLAS**
- Preguntas técnicas o conceptuales.
- Fix puntual de 1 archivo (typo, ajuste de copy, cambio cosmético).
- Lectura/exploración rápida de código sin intención de cambio.
- Comandos de terminal sueltos (status, logs, scripts).
- Tareas de menos de ~15 minutos sin acoplamiento sistémico.

**Regla**: ante la duda, Modo Rápido. Es más barato escalar a ATLAS que desactivarlo a mitad.

### Cómo operar en Modo Rápido
- No invocar al orquestador.
- No abrir sesión Engram (`mem_session_start`).
- Claude responde directo con sus tools básicas.
- Si surge complejidad oculta → cerrar Modo Rápido y reabrir como ATLAS (Modo Diagnóstico o Planificación).

---

## 3. Modos de ATLAS

| Modo | Activación | Fases ejecutadas | Output esperado | Escribe código |
|---|---|---|---|---|
| **Diagnóstico** | `"modo diagnóstico sobre X"` | descubrimiento (read-only) + síntesis | reporte estructurado, opcional persistido en Engram | ❌ NO |
| **Planificación** | `"modo planificación de X"` | Fase 1 + Fase 2 (parcial: arquitectura sin código) | tareas con criterios + arquitectura propuesta | ❌ NO |
| **Ejecución** | `"activá pipeline para X"` o `"nuevo proyecto completo: X"` | Fases 1 → 5 completas | proyecto desplegado | ✅ SÍ |
| **Modificación** | `"modo modificación sobre X"` | análisis + planificación ligera + mini Fase 3 + QA | cambios aplicados sobre proyecto existente | ✅ SÍ |

> Todos los modos excepto Diagnóstico pueden persistir decisiones en Engram. Diagnóstico es siempre read-only sobre el proyecto, pero PUEDE escribir su reporte a Engram bajo `topic_key` del proyecto.

---

## 4. Sintaxis canónica de invocación

| Intención | Frase explícita |
|---|---|
| Iniciar proyecto nuevo | `"activá el pipeline para [descripción]"` |
| Modificar proyecto existente | `"modo modificación sobre [proyecto]: [cambio]"` |
| Auditar sin tocar | `"modo diagnóstico sobre [proyecto] — solo lectura"` |
| Solo planear | `"modo planificación de [proyecto] — sin ejecutar"` |
| Salir de ATLAS | `"cerrá ATLAS"` o `"modo rápido"` |

Si la frase no encaja en ninguno de estos patrones → **se activa el Intent Clarifier** (paso 0).

---

## 5. Ciclo de cualquier modo

1. **Pre**: Intent Clarifier (ver `~/.claude/intent-clarifier.md`) si el brief es vago.
2. **Open**: orquestador abre sesión Engram con `topic_key` derivado del proyecto.
3. **Run**: orquestador delega a subagentes según pipeline. **Nunca trabaja inline**.
4. **Gate**: aprobación humana en checkpoints obligatorios (sección 6).
5. **Close**: `mem_session_end` + resumen ejecutivo al usuario.

---

## 6. Aprobaciones humanas obligatorias

ATLAS pausa y espera confirmación explícita en estos puntos:

| Checkpoint | Qué se aprueba |
|---|---|
| Fin de **Fase 1** (Planning) | Lista de tareas + criterios de aceptación |
| Fin de **Fase 2B** (Visual assets) | Brand identity + assets generados |
| Fin de **Fase 4** (Certificación) | Reporte reality-checker + métricas |
| **Fase 5** paso 1 (git) | Commit + push |
| **Fase 5** paso 2 (deploy) | Despliegue a producción |

> Sin aprobación → no avanza. Si el usuario está ausente, ATLAS persiste estado en Engram y termina sesión limpia.

---

## 7. Garantías

- **Read-only es read-only**: en Modo Diagnóstico, ningún subagente escribe sobre el proyecto. Si lo intenta, abortar fase.
- **Rollback documentado**: cada fase de cierre del propio sistema y cada cambio estructural deja backup en `~/.claude/backups/`.
- **Engram es la única fuente de verdad para decisiones**: lo que no quede en Engram, no se considera decidido.
- **Allowlist activa**: prompts de permiso solo en acciones destructivas (`sudo`, `rm -rf`).

---

## 8. Backlog e issues

- Archivados en `~/.claude/backlog/` (estructura formal pendiente, Fase 3 de cierre).
- Issue Context7 flapping: **RESUELTO** 2026-05-08 (instalación global + path estable).

---

## 9. MCPs operativos (2026-05-08)

| MCP | Host | Estado | Uso principal |
|---|---|---|---|
| `plugin:engram:engram` | Claude Code plugin + `~/bin/engram.exe` v1.15.10 | ✅ Connected | Memoria persistente cross-session |
| `playwright` | Claude Code (`npx playwright-mcp`) | ✅ Connected | QA visual, screenshots, evidence-collector |
| `context7` | Claude Code (`context7-mcp.cmd` global) | ✅ Connected | 21st.dev component snippets, docs de librerías |
| `magic-21st` | Claude Code (`@21st-dev/magic@latest` + API key) | ✅ Connected | **Generación activa** de componentes UI con `/ui ...` (frontend-developer, ui-designer) |

**API keys pendientes** (capacidades bloqueadas hasta configurarlas):
- `GEMINI_API_KEY` → image-agent, logo-agent (generación $0.02-0.04/img)
- `HF_TOKEN` → image-agent, logo-agent (fallback gratuito, FLUX.1)
- `REPLICATE_API_TOKEN` → video-agent (fondos animados LTXVideo)

---

## 10. Referencia externa

Benchmark de inspiración: `github.com/Emaleo0522/claude-vibecoding`. ATLAS adapta lo útil del benchmark; no lo copia ciegamente. Cualquier divergencia respecto al benchmark es **deliberada** y queda registrada en este documento o en `~/.claude/backups/issues/`.

---

## 11. Decisiones cerradas (vigentes hoy)

- Engram v1.15.10: dual-hosted (Claude Code plugin + Claude Desktop MCP) → misma DB `~/.engram/engram.db`. Aceptado 2026-05-08 (setup oficial `engram setup claude-code`).
- Context7: instalación global via `npm i -g @upstash/context7-mcp`. Path estable `%APPDATA%\npm\context7-mcp.cmd`. Resuelto 2026-05-08.
- 38 agentes y 14 hooks sincronizados con benchmark al 2026-05-08.
- Pixel Bridge y mejoras game-dev: descartadas como cierre, abordables solo bajo demanda.
- HyperFrames: evaluado como skill periférica opcional. Prerequisito: Node.js ≥ 22 (actual: 20.18) + FFmpeg.

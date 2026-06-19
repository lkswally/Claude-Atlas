# ATLAS — Sistema Vibecoding Híbrido

> **Boot loader delgado (F30).** Este archivo es el contexto always-on. El detalle
> operativo vive en referencias lazy — cargalas por demanda (mapa abajo). Nada de
> gobernanza se perdió; solo se reubicó. Ante la duda, **leé la referencia
> correspondiente antes de actuar** (escape hatch).

## Identidad

ATLAS es una capa OS sobre Claude Code / Claude Desktop: orquestador central
(1 coordinador + 24 subagentes), registries declarativos, capability router,
hooks de seguridad, healthcheck y release gates. Estado: **v1.0.0-rc2** (CI verde).

## Dos modos de trabajo

| Modo | Cuándo | Cómo activarlo |
|------|--------|----------------|
| **Claude normal** | Preguntas, fixes, revisiones, chat técnico | Por defecto — simplemente habla |
| **Orquestador operativo** | Proyectos completos de software end-to-end | *"activa el pipeline"*, *"modo orquestador"*, *"nuevo proyecto completo: X"* |

En modo orquestador, Claude adopta `~/.claude/agents/orquestador.md` (pipeline de
5 fases, delegación a subagentes, sin trabajo real inline). El dispatcher
`tools/atlas_dispatcher.py` **enforza** Return Envelope, phase gates y E2E flows
(detalle: `docs/atlas-operational-capabilities.md`).

## Principios no negociables

- **Regla de oro:** el orquestador NUNCA hace trabajo real (no lee/escribe código,
  no analiza arquitectura). Solo coordina. Cada token inline es contexto perdido.
- **Memoria o no pasó:** toda decisión significativa va a Engram con `topic_key`.
- **Fail-open:** cada feature tiene `ATLAS_*_DISABLED=1`; nada de ATLAS rompe el
  Claude base.
- **QA antes de push:** ninguna tarea dev avanza sin evidence-collector PASS.

### Pipeline (5 fases)
```
Fase 1  Planificación   → project-manager-senior
Fase 2  Arquitectura    → ux-architect → ui-designer + security-engineer
Fase 2B Assets visuales → brand-agent → logo + image + video (opcional)
Fase 3  Dev ↔ QA Loop  → dev-agents ↔ evidence-collector (3 reintentos)
Fase 4  Certificación   → seo + api-tester + performance + reality-checker
Fase 5  Publicación     → git (confirmación) → deployer (confirmación)
```
Model routing: **Opus** (orquestador, project-manager-senior, security-engineer,
game-designer, reality-checker), **Sonnet** (los demás). Cada agente lo declara en
su frontmatter. Detalle de pipeline: `.claude/agents/orquestador.md`.

## Reglas clave
- Solo el **orquestador** guarda DAG State en Engram
- Los subagentes guardan sus propios resultados en Engram con topic keys del proyecto
- Solo **evidence-collector** y **reality-checker** hacen QA visual
- Solo **git** hace commits/push — nunca un agente dev
- Solo **deployer** despliega (Vercel para web, EAS Build para mobile)
- git y deployer actúan **solo con confirmación del usuario** — pero si el mensaje original ya incluía "sube", "git", "deploy", "push", "publica" o similar, eso **ya es la confirmación**. No volver a preguntar.
- Si el orquestador devuelve una pregunta de confirmación sobre una acción que el usuario ya autorizó en su mensaje, main Claude debe continuar el agente con `SendMessage` respondiendo la respuesta implícita — no dejar el agente suspendido.
- Cada tarea dev pasa por **evidence-collector** antes de avanzar (máx 3 reintentos)
- **El orquestador NO activa git hasta que evidence-collector retorna PASS** — nunca saltear QA antes de push, aunque el tiempo apremia. Los bugs silenciosos (Mixed Content, fallback invisible) solo se detectan con QA.
- **codepen-explorer solo busca y extrae** — nunca adapta ni construye. Guarda código temporal en `{project_dir}/.codepen-temp/{slug}/`. frontend-developer lee de ahí y adapta al proyecto/brand.
- **Bóveda CodePen** (`~/.claude/codepen-vault/`) — solo guarda efectos aprobados por el usuario. Engram tiene metadata buscable (`codepen-vault/{slug}`), disco tiene el código.
- **Checkpoint post-efectos en Fase 3** — si se usaron efectos de CodePen, mostrar página completa al usuario antes de pasar a Fase 4 para que pueda pedir cambios.

## Seguridad esencial (hooks en tiempo real)

Los hooks (`.claude/hooks/`, en `~/.claude/settings.json`) interceptan tool calls.
Comportamiento: Exit 2 = BLOCK | Exit 0 + stderr = WARN | fail-open.
- `block-no-verify` **BLOQUEA** `git --no-verify`, `rm -rf`, `git reset --hard`, `DROP TABLE`, `chmod 777`, `curl|sh`.
- `config-protection` **BLOQUEA** secrets (`.env`, `.pem`, `.key`).
- `quality-gate` / `console-log-warning` **ADVIERTEN**.

Tabla completa de 13 hooks + utilidades: `docs/atlas-operational-capabilities.md`.

## Engram (memoria persistente) — esencia

Lectura SIEMPRE en 2 pasos (`mem_search` → `mem_get_observation`, nunca preview
truncada). Escritura SIEMPRE con `topic_key`. Dual-write crítico (Engram + disco
`.pipeline/`). Protocolo completo, resiliencia y cajones críticos:
**`docs/atlas-engram-reference.md`**.

## Protocolo de subagentes

Todo subagente sigue `~/.claude/agents/agent-protocol.md` (Engram 2-pasos,
`topic_key` obligatorio, Return Envelope estándar). No duplicar esos patrones.

## Mapa de referencias (cargar por demanda)

| Cuando necesites… | Leé |
|-------------------|-----|
| Por qué/ cómo carga el boot, escape hatch | `docs/atlas-boot-reference.md` |
| Capacidades operativas, dispatcher, design-quality, hooks, tools por agente | `docs/atlas-operational-capabilities.md` |
| Protocolo Engram completo | `docs/atlas-engram-reference.md` |
| Release gates, RC, CI, warnings permitidos, estados (PASS/WARN/SKIP/…) | `docs/atlas-release-reference.md` |
| Stack, Nothing DS, Better Auth, agentes creativos, best practices, **overrides Windows** | `docs/atlas-build-reference.md` |
| Pipeline de 5 fases (comportamiento) | `.claude/agents/orquestador.md` |
| Contrato de subagente | `.claude/agents/agent-protocol.md` |
| Refs técnicas (GSAP, React, PocketBase, Redis, scroll, audio, creative coding…) | `.claude/agents/*-reference.md` |

> **Windows / Claude Desktop:** NO arrancar servers con `npm run dev` vía Bash —
> usar `preview_start` del Claude Preview MCP. Reglas completas de Windows en
> `docs/atlas-build-reference.md`.

## Comandos mínimos

```bash
python tools/atlas_healthcheck.py          # salud del sistema (exit 0 = HEALTHY)
python tools/run_all.py --quick            # validación de desarrollo (~30 suites)
python tools/run_all.py --release          # gate antes de publicar/taggear
python tools/secrets_check.py              # tokens configurados vs pendientes
```

## Escape hatch

Si vas a actuar y te falta el detalle operativo del caso (gobernanza, release,
Engram, Windows, build), **leé primero la referencia del mapa** — no improvises
desde memoria. CLAUDE.md tiene lo esencial; las referencias tienen las reglas
completas.

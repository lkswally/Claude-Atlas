# Upgrade Log — Context Management + Best Practices

## v2.2 — Context Window Optimization — 2026-04-08

### Summary
Two targeted improvements to context window management, inspired by analysis of [MemPalace](https://github.com/milla-jovovich/mempalace) architecture. Zero new dependencies, zero protocol changes for sub-agents.

### Changes

**1. PreCompact Blocking (pre-compact-engram.js)**
- Hook now emits "COMPACTION IMMINENT -- SAVE STATE NOW" via stderr before compaction
- Instructs the orchestrator to do dual-write (Engram + disk) before context is lost
- Detects active pipeline by reading `.pipeline/estado.yaml` for current phase/task
- Includes pipeline status in the stderr message for context
- Previous behavior: only saved metadata snapshot (tool count, cwd) passively
- New behavior: actively forces state preservation before compaction

**2. Progressive DAG State Loading (orquestador.md Boot Sequence)**
- Boot Sequence now loads DAG State in 2 levels: light (~50-100 tokens) vs full (~500-2000 tokens)
- Light boot: fase_actual + tarea_actual/total + stack 1-liner + ultimo_save
- Full boot: only when orchestrator needs to make coordination decisions (phase transitions, escalations, scope changes)
- Orchestrator retains observation_id for on-demand re-reads, discards full YAML from context
- No changes needed in sub-agents -- they still read their specific drawers in full via 2-step pattern

### Files modified
- `hooks/pre-compact-engram.js` — rewritten with pipeline detection + stderr blocking message
- `agents/orquestador.md` — Boot Sequence rewritten with 2-level progressive loading + PreCompact v2.2 note
- `CLAUDE.md` — 3 sections updated (Carga progresiva, hook table, Resiliencia Engram)
- `README.md` — New "Context Window Management (v2.2)" section + hook table updated

### Audit result
6/6 PASS (syntax, consistency across 3 files, settings.json integration, agent-protocol compatibility, cross-references)

---

## Auditoria v3 — 2026-03-30

### Resumen
Auditoria arquitectonica completa del sistema post-adicion de codepen-explorer y agent-protocol. 18 fixes aplicados en 15 archivos. Re-auditoria verifico 0 issues pendientes.

### Fixes HIGH (4)
- **H1**: codepen-explorer migrado de Chrome MCP (no configurado) a Playwright MCP
- **H2**: CLAUDE.md conteo corregido "1+21=22" → "1+22=23". Seccion "Referencias tecnicas" agregada (7 archivos). codepen-explorer en tabla de coordinacion.
- **H3**: settings.local.json — `rm:*` restringido a patrones seguros, `sudo` → ask, permisos muertos eliminados, `mv:*` y `browser_install` agregados
- **H4**: MEMORY.md alineado con realidad (3 cajones creativos separados)

### Fixes MEDIUM (9)
- **M1**: STATUS utilitarios (OK/SAVED/FOUND/NOT_FOUND/BLOCKED) en agent-protocol.md y orquestador validacion
- **M2**: Camino muerto "Fase 2B paralela" eliminado. Step numbers CodePen corregidos (1-6)
- **M3**: DAG State: a11y/bundle/lint → null defaults. Bloque `codepen:` agregado. costs con mem_save explicito
- **M4**: `project` param en mem_save de 5 agentes Fase 3-4 (evidence-collector, reality-checker, api-tester, performance-benchmarker, seo-discovery)
- **M6**: DrawSVGPlugin "GSAP Club required" → "incluido desde 2025"
- **M8**: Rollback en git.md (git revert) y deployer.md (vercel promote)
- **M9**: evidence-collector retry self-guard (rechaza intento > 3)
- agent-protocol.md regla 1 con Windows guard
- Recovery post-compactacion simplificado

### Fixes LOW (2 aplicados, 3 mantenidos por diseno)
- **L5**: ux-architect description "junto con" → "ANTES de"
- **L6/L7**: Monorepo detection 4x y retry block 7x MANTENIDOS — diseno hub-and-spoke requiere agentes autocontenidos

### Re-auditoria (3 fixes adicionales)
- `Bash(done)` remanente eliminado de settings.local.json
- codepen-explorer tool table en CLAUDE.md expandida a 6 tools Playwright
- security-engineer en orquestador: "nada" → `{proyecto}/tareas`

### Archivos modificados
agent-protocol.md, api-tester.md, codepen-explorer.md, deployer.md, evidence-collector.md, git.md, orquestador.md, performance-benchmarker.md, reality-checker.md, seo-discovery.md, ux-architect.md, CLAUDE.md (x3 con templates), settings.local.json

### Sync repo (2026-03-30)
- README.md reescrito (conteos, codepen-explorer, coordinacion, topic keys, refs)
- install/linux.sh conteos corregidos (23+7)
- install/windows.md conteos corregidos (23+7)
- UPGRADE_LOG.md actualizado

---

## Fecha: 2026-03-23

---

## Fase 1: Context Management Foundation ✅ COMPLETADA

### 1.1 Boot Sequence ✅
- Archivo: agents/orquestador.md (linea 12)
- Agrega deteccion automatica de proyecto existente al inicio de cada interaccion
- Busca en Engram antes de asumir proyecto nuevo
- Incluye mem_session_start obligatorio

### 1.2 Session Lifecycle ✅
- Archivo: agents/orquestador.md (linea 58)
- Tres fases: arranque (session_start), durante (saves proactivos), cierre (session_summary + session_end)
- Pre-resolucion de topic keys incluida aqui (cache de observation_ids)
- Regla de 3 delegaciones: si pasaron 3+ sin guardar DAG → guardar ahora

### 1.3 DAG State granular ✅
- Archivo: agents/orquestador.md (seccion DAG State)
- Campos nuevos: tarea_actual, ultimo_save, drawer_ids, backup_disk
- Cambio de "guardar por fase" a "guardar por tarea completada"
- Backward-compatible: campos nuevos son opcionales en YAML

### 1.4 Context Health Check ✅
- Archivo: agents/orquestador.md (linea 724)
- Checklist de 3 puntos antes de cada delegacion en Fase 3
- Previene perdida de progreso si compactacion ocurre mid-delegacion

### 1.5 Proactive Save Mandate ✅
- Archivo: agents/orquestador.md (en seccion Engram)
- Define formato discovery: What/Why/Where/Learned
- Topic key: {proyecto}/discovery-{descripcion-corta}
- Instruccion para subagentes de guardar hallazgos inmediatamente

---

## Fase 2: Agent Communication Protocol ✅ COMPLETADA

### 2.1 Return Envelope Standard ✅
- Archivo: agents/orquestador.md (linea 636) + 21 agentes
- 4 formatos: Dev, QA, Fase4, Fase5
- Cada agente tiene su copia del formato correcto

### 2.2 Canonical 2-step Read ✅
- Archivo: CLAUDE.md (seccion Engram)
- Bloque de pseudocodigo unico de referencia
- Disponible para todos los agentes

### 2.3 Proactive Save en cada agente ✅
- 21 archivos de agentes actualizados
- Seccion "Proactive saves (discoveries)" con formato mem_save
- Verificado: 21 archivos tienen la seccion

---

## Fase 3: Token Optimization ✅ COMPLETADA

### 3.1 Pre-resolucion topic keys ✅
- Integrado en Session Lifecycle (1.2)
- Cache de observation_ids en DAG State (campo drawer_ids)
- Subagentes reciben obs_id directamente, saltan mem_search

### 3.2 Handoff optimizado ✅
- Archivo: agents/orquestador.md (Fase 3, paso 3)
- Formato compacto con obs_ids pre-resueltos
- Referencia a Return Envelope en vez de repetir formato

---

## Fase 4: Robustness ✅ COMPLETADA

### 4.1 Dual-write cajones criticos ✅
- Archivo: agents/orquestador.md (seccion Graceful Degradation)
- estado + tareas se escriben en Engram + disco ({project_dir}/.pipeline/)
- Fallback: si Engram falla → leer de disco

### 4.2 Inter-session continuity ✅
- Archivo: CLAUDE.md (seccion "Continuidad entre sesiones")
- Protocolo para retomar proyecto en nueva conversacion
- Cualquier persona puede retomar leyendo DAG State

---

## Archivos modificados (resumen)

| Archivo | Cambios aplicados |
|---------|------------------|
| agents/orquestador.md | Boot Sequence, Session Lifecycle, DAG granular, Health Check, Proactive Save, Return Envelope, Handoff optimizado, Dual-write |
| CLAUDE.md | Canonical 2-step read, Inter-session continuity, DAG por tarea, Proactive saves, Dual-write |
| 21 agentes restantes | Proactive saves + Return Envelope (formato por tipo) |

## Verificacion

- [x] 21 agentes con "Proactive saves": confirmado
- [x] 22 agentes con "Return Envelope": confirmado (21 + orquestador)
- [x] Boot Sequence en orquestador: confirmado
- [x] Session Lifecycle en orquestador: confirmado
- [x] Canonical read block en CLAUDE.md: confirmado
- [x] Inter-session continuity en CLAUDE.md: confirmado
- [x] 23 archivos copiados a ~/.claude/agents/: confirmado
- [x] CLAUDE.md copiado a ~/CLAUDE.md: confirmado

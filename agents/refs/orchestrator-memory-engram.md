# Orchestrator — Session Lifecycle & Engram Memory

> Lazy reference extracted from orquestador.md in F32 (knowledge decomposition).
> Load when the orchestrator facade points here. Content verbatim — behavior unchanged.

## Session Lifecycle (OBLIGATORIO — protege continuidad entre sesiones)

### Al arrancar
Cubierto por Boot Sequence arriba. Siempre se ejecuta `mem_session_start`.

### Durante la sesion — saves proactivos
Despues de CADA evento significativo, guardar DAG State inmediatamente:
- Fase completada → `mem_update` de `{proyecto}/estado`
- Tarea completada (QA PASS) → `mem_update` de `{proyecto}/estado`
- Decision del usuario (cambio scope, aprobacion marca) → `mem_update` de `{proyecto}/estado`
- Error critico o escalacion → `mem_update` de `{proyecto}/estado`

**Regla**: si pasaron mas de 3 delegaciones a subagentes sin guardar DAG State → guardar AHORA.

### Al finalizar sesion (o si el usuario dice "paramos aca")
1. Guardar DAG State actualizado con `mem_update`
2. Llamar `mem_session_summary` con formato obligatorio:
```
mem_session_summary(
  project: "{proyecto}",
  content: "## Goal\n{que estabamos construyendo}\n\n## Discoveries\n- {hallazgo 1}\n- {hallazgo 2}\n\n## Accomplished\n- {tarea completada 1}\n- {tarea completada 2}\n\n## Next Steps\n- {que falta hacer}\n\n## Relevant Files\n- {archivo 1} — {que cambio}"
)
```
3. Llamar `mem_session_end(id: "vibecoding-{proyecto}-{timestamp}")`

**NOTA**: `mem_session_end` es responsabilidad EXCLUSIVA del orquestador, no de hooks (los hooks no pueden llamar MCPs). Si la sesion termina abruptamente (Ctrl+C, crash), la sesion queda abierta en Engram — el Boot Sequence de la siguiente sesion detecta esto y la cierra retroactivamente.

**Esto permite que CUALQUIER persona (u otra sesion de Claude) retome el proyecto leyendo el session summary + DAG State.**

---

## Sistema de Memoria — Cajones Engram

### Nombres de cajones (topic keys)
> Cajones más usados por el orquestador:
> `{proyecto}/estado`, `{proyecto}/tareas`, `{proyecto}/branding`, `{proyecto}/creative-images`, `{proyecto}/creative-logos`, `{proyecto}/creative-video`, `{proyecto}/certificacion`, `{proyecto}/costs`

### Protocolo de Engram — Proteger el contexto

> Protocolo de lectura/escritura 2-pasos: ver `agent-protocol.md` §1-2. Aqui solo las reglas adicionales del orquestador.

**Reglas de contexto del orquestador:**
1. **No duplicar en contexto**: pasar topic_key al subagente, no contenido
2. **Cajones atómicos**: un propósito por cajón. No mezclar tareas con decisiones
3. **Stack va en estado**: se guardan en `{proyecto}/estado`, no en cajón aparte
4. **Subagentes leen solo sus cajones** (ver tabla abajo)

**Qué cajón lee cada agente:**
| Agente | Lee de Engram | Escribe en Engram |
|--------|--------------|-------------------|
| project-manager-senior | nada (recibe spec directa) | `{proyecto}/tareas` |
| ux-architect | `{proyecto}/tareas` | `{proyecto}/css-foundation` |
| ui-designer | `{proyecto}/css-foundation`, `{proyecto}/visual-direction` | `{proyecto}/design-system` |
| security-engineer | `{proyecto}/tareas` | `{proyecto}/security-spec` |
| frontend-developer | `{proyecto}/css-foundation`, `{proyecto}/visual-direction`, `{proyecto}/design-system`, `{proyecto}/security-spec`, `{proyecto}/tareas`, `codepen-vault/*` (consulta boveda), capability `documentation` (21st.dev, si `component_source: 21st.dev`) | `{proyecto}/tarea-{N}` |
| mobile-developer | `{proyecto}/design-system`, `{proyecto}/tareas` | `{proyecto}/tarea-{N}` |
| backend-architect | `{proyecto}/security-spec`, `{proyecto}/tareas` | `{proyecto}/tarea-{N}` |
| rapid-prototyper | `{proyecto}/tareas` (la tarea específica) | `{proyecto}/tarea-{N}` |
| game-designer | nada (recibe spec de mecánicas) | `{proyecto}/gdd` |
| xr-immersive-developer | `{proyecto}/gdd`, `{proyecto}/css-foundation` | `{proyecto}/tarea-{N}` |
| brand-agent | nada (recibe brief directo) | `{proyecto}/branding` |
| logo-agent | nada (lee brand.json del filesystem) | `{proyecto}/creative-logos` |
| image-agent | nada (lee brand.json del filesystem) | `{proyecto}/creative-images` |
| video-agent | nada (lee brand.json + hero.png del filesystem) | `{proyecto}/creative-video` |
| seo-discovery | `{proyecto}/tareas` (estructura de páginas) | `{proyecto}/seo` |
| evidence-collector | `{proyecto}/tarea-{N}` (criterios de la tarea) | `{proyecto}/qa-{N}` |
| api-tester | `{proyecto}/api-spec` (generado por backend-architect; sin fallback — si no existe, el orquestador re-delega a backend-architect para generarlo) | `{proyecto}/api-qa` |
| performance-benchmarker | nada (recibe URL) | `{proyecto}/perf-report` |
| reality-checker | todos los cajones del proyecto | `{proyecto}/certificacion` |
| git | nada (recibe directorio + mensaje) | `{proyecto}/git-commit` |
| deployer | nada (recibe directorio + nombre) | `{proyecto}/deploy-url` |
| codepen-explorer | `codepen-vault/*` (consulta boveda) | `codepen-vault/{slug}` (solo al guardar en boveda) |

**NUNCA pasar al subagente**: contenido de otros subagentes, historico de conversacion, resultados de QA anteriores, codigo inline.

### Proactive Save Mandate (para subagentes)

> Formato de discoveries: ver `agent-protocol.md` §4. El orquestador NO lee discoveries por defecto — son para busqueda futura (`mem_search`).

### DAG State — guardar despues de CADA TAREA completada (no solo fases)

**Regla critica**: el DAG State se actualiza despues de CADA tarea que pasa QA, no solo al final de cada fase. Esto garantiza que si la sesion se compacta en la tarea 5 de 8, las tareas 1-4 no se pierden.

```yaml
proyecto: "nombre-del-proyecto"
tipo: "web | app | mobile | juego | api"
estructura: "single-repo | monorepo"
stack:
  frontend: "Next.js | SvelteKit | Vite+React | Astro | Phaser.js | none"
  backend: "Hono | Express | Fastify | none"
  db: "PostgreSQL | SQLite | Supabase | none"
  orm: "Drizzle | Prisma | none"
  api: "tRPC | REST | GraphQL | WebSocket"
  auth: "Better Auth | none"
  extras: ["BullMQ", "Redis", "Socket.IO"]  # opcionales segun necesidad
  game_engine: "Phaser.js | PixiJS | Three.js | Canvas | none"  # solo si tipo=juego
  game_subsystems: []  # subsistemas del GDD: [entity, event, fsm, scene, sound, pool, ...]
  design_system: "nothing-full | nothing-partial | custom | none"  # nothing-full=todo el proyecto, nothing-partial=solo secciones listadas en nothing_scope, custom=design propio (default), none=sin design system
  nothing_scope: []    # solo si design_system=nothing-partial — lista de secciones/componentes: ["hero", "dashboard", "stats-section", "footer"]
  component_source: "21st.dev | codepen | custom | none"  # 21st.dev=consultar community components via Context7, codepen=buscar en CodePen vault/explorer, custom=todo manual (default), none=sin componentes pre-hechos
fase_actual: "fase_1_planificacion | fase_2_arquitectura | fase_2b_assets | fase_3_dev | fase_4_certificacion | fase_5_publicacion | completado | modificacion"
fases_completadas:
  planificacion: null             # observation_id (numero) o null si no completada
  arquitectura:
    css: null                     # observation_id del css-foundation
    visual_direction: null        # observation_id del visual-direction (elecciones del usuario)
    design: null                  # observation_id del design-system
    security: null                # observation_id del security-spec
  assets_creativos:
    necesarios: false             # true si el proyecto tiene landing/logo/hero
    branding: "pendiente"         # "pendiente" | observation_id
    image_backend: "huggingface"  # "gemini" | "huggingface"
    logo: "pendiente"             # "pendiente" | "listo" | "no-requerido"
    images: "pendiente"           # "pendiente" | "listo" | "no-requerido"
    video: "pendiente"            # "pendiente" | "listo" | "no-requerido"
desarrollo:
  total_tareas: 0
  tarea_actual: 0                 # cual tarea esta en progreso ahora mismo
  tareas_completadas: []          # [1, 2, 3] — numeros de tarea
  tareas_en_progreso: []          # [4] — max 1 normalmente
  tareas_fallidas: []             # [{tarea: 5, intentos: 3, motivo: "..."}]
  ultimo_save: ""                 # ISO timestamp del ultimo update de DAG State
certificacion:
  seo: null                       # observation_id del seo-discovery
  seo_tier: "pending"             # "pending" | "structural" | "full" — progreso del SEO por tiers
  api_tester: null                # observation_id del api-qa
  performance: null               # observation_id del perf-report
  reality_checker: null           # observation_id de certificacion
  a11y_violations: 0              # axe-core critical/serious (0 = PASS)
  bundle_size_pass: true          # bundlewatch gate (opcional, solo si hay build JS)
  lint_pass: true                 # eslint/stylelint gate
publicacion:
  git_commit: null                # observation_id del git-commit
  deploy_url: null                # observation_id del deploy-url
# Campos anti-loop (se incrementan, nunca resetear a 0 mid-pipeline)
phase_gate_retries: 0             # re-delegaciones por Phase Gate (max 2 compartido con Fase 2)
recertification_cycles: 0         # ciclos NEEDS WORK→fix→re-certify (max 3)
# Campos de modo modificación (solo si fase_actual = "modificacion")
modificacion_tareas: []           # [13, 14, 15] — IDs de las nuevas tareas
modificacion_origen: ""           # "completado" — fase desde la que se inició
# Campos de estado del sistema
backup_disk: ""                   # ruta al backup en disco (ver Dual-Write)
recovered: false                  # true si esta sesion retomo tras crash/compactación
qa_mode: "full"                   # "full" | "code-only" (si capability browser no está LIVE — resolve_capability("browser").status not in LIVE/CONFIG_ONLY)
engram_degraded: false            # true si Engram tuvo fallas en esta sesion
```

**Cuando guardar DAG State (mem_update):**
- Despues de cada fase completada
- Despues de cada tarea que pasa QA (PASS)
- Despues de cada decision del usuario (scope, marca, stack)
- Despues de cada escalacion (FAIL 3x)
- Si pasaron 3+ delegaciones sin guardar → guardar AHORA

**Dual-write obligatorio (CLAUDE.md §Engram):**
Despues de CADA `mem_update` de `{proyecto}/estado`, escribir tambien a disco:
```
Write("{project_dir}/.pipeline/estado.yaml", dagStateYaml)
```
Esto garantiza que si Engram falla o la sesion crashea, el DAG State se puede recuperar del filesystem. El Boot Sequence busca primero en Engram, luego en `.pipeline/`.

---


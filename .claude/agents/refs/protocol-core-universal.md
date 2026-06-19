# Protocol — Universal Rules, Design Intelligence, Anti-Generic, Limits, Anti-Loop

> Lazy reference extracted from agent-protocol.md in F32 (knowledge decomposition).
> Load when the protocol facade points here. Content verbatim — behavior unchanged.

## 5. Reglas universales (todos los subagentes)

1. **No arrancar servidores con Bash** → usar `preview_start` (solo aplica en Windows/Claude Desktop; en Linux/Claude Code CLI, usar Bash normalmente)
2. **No hacer git commit/push** → solo el agente `git` hace esto
3. **No deployar** → solo el agente `deployer` hace esto
4. **No usar imágenes de placeholder** (picsum.photos, lorem picsum, etc.) → usar assets reales del proyecto o generar con agentes creativos
5. **Asumir que no hay proceso corriendo en el puerto** → verificar/matar antes de levantar servidor
6. **Resúmenes cortos al orquestador** → nunca código completo, nunca archivos enteros
7. **No duplicar lo que ya está en Engram** → pasar topic_key, no contenido

---

## 6. Design Intelligence Queries — Patrón Universal

### Qué es

Design Intelligence es un motor local (BM25) que recomendaciones de diseño basadas en la industria/tipo de proyecto. Vive en `~/.claude/design-data/search.js` con 8 CSVs de datos: styles, colors, typography, charts, landing, products, ux-guidelines, reasoning.

**Úsalo cuando**:
- ux-architect necesita fondación CSS parametrizada (Paso 0)
- ui-designer necesita dirección estética y componentes (Paso 0a-0b)
- frontend-developer necesita specs de motion/animation tiers (consultas opcionales)

**NO usar Design Intelligence para**:
- Componentes específicos (eso es 21st.dev)
- Refactoring de código existente
- Optimizaciones de performance

### Patrón de invocación

```bash
node ~/.claude/design-data/search.js "{tipo}" [opciones] -p "{proyecto}"
```

**Argumentos obligatorios**:
- `{tipo}`: industria/tipo de producto (ej: "mental-health", "e-commerce", "finance", "saas")
- `-p {proyecto}`: nombre del proyecto (para contexto de guardado)

**Opciones comunes**:
- `--design-system`: retorna recomendaciones de CSS foundation (default)
- `--domain chart`: retorna recomendaciones de data visualization (charts, SVG, canvas thresholds)
- `--domain ux`: retorna UX guidelines (accessibility, forms, interactions)
- `--domain preset`: retorna preset específico (mood_preset como argumento primario, ej: `"swiss-minimal"`)
- `--strict`: descarta sugerencias genéricas (teal-saas, default patterns)
- `-n {N}`: número máximo de resultados (default 1)

### Validación de resultado

**SIEMPRE validar** antes de usar:

```
Validación A — JSON bien formado
  IF JSON parse error:
    ❌ Reintenta query con --strict
    ❌ Si falla de nuevo, usa defaults + documentar fallback

Validación B — Campos obligatorios presentes
  REQUERIDOS: anti_patterns (array), style.name (string), colors (object)
  IF alguno missing:
    ❌ BLOQUEAR — el motor retornó respuesta incompleta

Validación C — No-generic check (SOLO para moods audaces)
  IF intent.mood_preset NOT IN [swiss-minimal, dashboard-dense]:
    AND style.name IN [teal-saas, minimal-generic, default-bootstrap]:
      ⚠️ ADVERTENCIA — proceder pero esperar guardrails T1-T7 (ui-designer línea 94)
      ALTERNATIVA: re-ejecutar con --strict --mood={mood_preset}

Validación D — Anti-patterns no-vacío
  IF anti_patterns.length == 0:
    ❌ BLOQUEAR — re-ejecutar con --strict
```

### Guardar a Engram (OBLIGATORIO)

```
mem_save(
  title: "{proyecto}/design-intelligence",
  topic_key: "{proyecto}/design-intelligence",
  type: "discovery",
  content: """
  **Tipo consultado**: {tipo}
  **Estilo detectado**: {style.name}
  **Validación**: {PASS | FALLBACK}
  
  Anti-patterns (OBLIGATORIOS):
  {listar array}
  
  Colores recomendados:
  {listar objeto}
  
  Tipografía:
  {pares tipográficos}
  """,
  project: "{proyecto}"
)
```

**Formato alternativo corto** (si memória está tight):
```
mem_save(
  title: "{proyecto}/design-intelligence",
  topic_key: "{proyecto}/design-intelligence",
  type: "discovery",
  content: "[JSON result stringified]",
  project: "{proyecto}"
)
```

### Manejo de errores

| Escenario | Acción |
|-----------|--------|
| Query retorna JSON vacío | Re-ejecutar con `--strict`. Si sigue vacío, usar defaults (Minimalism) + documentar fallback en Engram |
| Anti-patterns vacío | BLOQUEAR — el motor está roto. Informar a orquestador |
| Style genérico para mood audaz | ADVERTENCIA en Engram + proceder bajo responsabilidad. Guardrails T1-T7 pueden bloquear |
| Brand.json existe pero style incoherente | Consultar a orquestador antes de proceder (guardar issue en Engram) |

---

## 7. Anti-Generic 21st.dev Validation — Patrón Universal

### Qué es

21st.dev es un marketplace de componentes React. Los componentes son versátiles pero pueden ser genéricos (teal SaaS, default patterns) si se usan sin validación.

**Para evitar componentes genéricos**: aplicar validación PRE y POST consulta contra mood_preset, brand.json, anti_patterns.

### Cuándo usar 21st.dev

**Úsalo cuando**:
- frontend-developer necesita inspiración de componentes interactivos (hover states, micro-interactions)
- El handoff incluye `COMPONENT_SOURCE: 21st.dev`
- Proyecto requiere motion/animation tiers ≥4 (Framer Motion o GSAP)

**NO usar para**:
- Componentes básicos (botones, inputs) — generar custom
- Componentes que existan en shadcn/ui
- Clon de designs existentes sin creatividad

### Patrón de validación PRE-consulta (frontend-developer responsibility)

Antes de consultar 21st.dev, validar:

```
Validación 1 — Coherencia con Brand
  IF brand.json existe:
    VERIFICAR que mood_vector es audaz (luxury, editorial, immersive, etc.)
                OR design_variance ≥ 5
    IF mood_vector es minimal/corporate (ej: {swiss: 8, minimal: 6, luxury: 1}):
      ⚠️ 21st.dev puede ser overkill — usa custom CSS + Framer Motion simple
      PROCEED ONLY IF animation_intensity ≥ 4 AND no hay anti_patterns HIGH

Validación 2 — Anti-patterns
  READ anti_patterns array desde Design Intelligence
  IF consulting 21st.dev would violate any:
    ❌ SKIP 21st.dev — implementar custom
    EXAMPLE: si anti_patterns = ["gradient-overuse", "shadow-gloss"]
             y 21st.dev result tiene ambos → rechazar

Validación 3 — Motion tier coherence
  IF motion_intensity ≤ 3:
    ❌ SKIP 21st.dev (probablemente overengineered) — usar CSS + Framer Motion simple
  IF motion_intensity 4-6:
    ✅ 21st.dev OK pero validar que sea Framer Motion o CSS, no GSAP
  IF motion_intensity ≥ 7:
    ✅ 21st.dev OK, puede ser GSAP + Lenis + SplitText
```

### Patrón de consulta

```
Paso 1: Resolver library ID
resolve-library-id("21st.dev") → {library_id}

Paso 2: Consultar con constraints
query-docs(
  libraryId: {library_id},
  query: "{tipo de componente} hover state animation {mood_preset}"
)

EJEMPLO: "card component with scale hover animation for editorial design"
```

### Patrón de validación POST-consulta (adaptación)

Después de obtener componente de 21st.dev:

```
Paso 1 — Extraer código
  Leer el component code del resultado

Paso 2 — Verificar contra anti_patterns
  FOR each anti_pattern IN anti_patterns_HIGH:
    IF component contiene anti_pattern:
      ❌ RECHAZAR — no usar componente, implementar custom
      EJEMPLO: si anti_pattern="gradient-overuse"
               y component tiene `background: linear-gradient(...)`:
               → rechazar y avisar a user

Paso 3 — Adaptar colores a brand.json
  FOR each color property EN component:
    REEMPLAZAR con tokens de brand.json
    EJEMPLO: `--color-primary: #...` → `--color-primary: var(--brand-primary)`

Paso 4 — Adaptar tipografía
  IF typography.family en component != brand.json.typography_pair:
    REEMPLAZAR con brand fonts + sizes

Paso 5 — Adaptar spacing/sizing a design-foundation
  MAPEAR `padding`, `margin`, `gap` a escalas de css-foundation
  EJEMPLO: `padding: 24px` → `padding: var(--space-6)` (si --space-6 = 24px)

Paso 6 — Guardar descobrimiento
  mem_save(
    title: "{proyecto}/component-adaptation-21st.dev",
    topic_key: "{proyecto}/discovery-21st-{component-name}",
    type: "discovery",
    content: """
    **Componente**: {nombre}
    **Adaptaciones**: {lista}
    **Anti-patterns validados**: {PASS | FALLIDO}
    **Brand alignment**: {PASS | FALLIDO}
    """,
    project: "{proyecto}"
  )
```

### Manejo de bloqueos

| Caso | Acción |
|------|--------|
| 21st.dev component contiene anti_pattern | Rechazar componente. Implementar custom. Informar en Return Envelope |
| Colores no adaptables a brand | Implementar custom. Anti-generic guardrail es HARD |
| Motion tier incoherente (ej: GSAP para motion≤3) | Descartar y usar librería más simple (CSS, Framer simple) |
| Componente es SaaS generic pattern | Validar contra T1-T7 guardrails (ui-designer). Si falla, rechazar |

---

## 8. Límites universales (lo que NINGÚN subagente hace)

- No tomar decisiones de arquitectura que no te correspondan
- No modificar archivos fuera del scope de tu tarea
- No instalar dependencias no solicitadas
- No leer cajones de Engram que no necesitas (lee solo los listados en tu sección "Inputs")
- No crear archivos de documentación (README, CHANGELOG) salvo que la tarea lo pida

---

## 9. Anti-Loop Tracking (Intra-Sesión) — Enforcement (Bloque 1A.12)

**NIVEL**: Intra-sesión (previene loops dentro de la sesión actual). NO persiste entre sesiones aún.

**QUÉ ES**: Mecanismo para prevenir reintentos infinitos si un cajon falta persistentemente durante una sesión.

**CÓMO FUNCIONA**:
- Dispatcher mantiene contador `phase_gate_retries` por cajon
- Si cajon falta en enforce_phase_gate():
  - Intento 1: falta → añade a missing_cajones, incrementa counter
  - Intento 2: falta → añade a missing_cajones, incrementa counter
  - Intento 3+: falta → ESCALACIÓN (no re-delega, escala a usuario)

**COMPORTAMIENTO POR INTENTO**:

| Intento | Contador | Acción | Resultado |
|---------|----------|--------|-----------|
| 1 | 0 → 1 | Añade cajon a missing, redel agente | Re-delegación con feedback |
| 2 | 1 → 2 | Añade cajon a missing, redel agente | Re-delegación con feedback |
| 3+ | 2+ | ESCALACIÓN (no añade a missing) | Requiere intervención usuario |

**ESCALACIÓN**: Si cajon sigue faltando tras 2+ intentos:
```
FASE X ESCALACIÓN (Max reintentos alcanzado):
  Cajones bloqueados tras 2+ intentos: {proyecto}/tareas (intento 3/max 2)
  Acción requerida: Usuario debe resolver manualmente o reasignar agente
```

**RESET DEL CONTADOR**:
- Si cajon aparece (found) después de falta → contador se resetea a 0
- Si Engram timeout + disk fallback existe → contador se resetea a 0
- Cuando cajon está OK en la siguiente gate check, el contador desaparece

**RESPONSABILIDAD**:
- Dispatcher: mantiene contador y decide escalación
- Orquestador: lee escalación_cajones y presenta opciones al usuario
- Usuario: resuelve (ej: crear cajon manualmente, reasignar agente, diferir tarea)

**LIMITACIÓN ACTUAL**:
- Counter es session-local (memoria del dispatcher)
- Si sesión termina → counter se pierde
- Si usuario retoma proyecto en sesión nueva → counter = 0 (reinicia)

**ANTI-LOOP ENTRE SESIONES** (futuro):
- Persistir counter en Engram/DAG State
- Cargar counter en Boot Sequence
- Detectar si cajon ya falló 2+ veces en sesión anterior
- Bloque 1A.13+: implementará persistencia entre sesiones

---


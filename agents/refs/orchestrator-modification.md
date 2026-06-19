# Orchestrator — Modification Mode

> Lazy reference extracted from orquestador.md in F32 (knowledge decomposition).
> Load when the orchestrator facade points here. Content verbatim — behavior unchanged.

## Modo Modificación (proyectos existentes)

Cuando el usuario pide **modificar, agregar o quitar features de un proyecto ya completado** (no un proyecto nuevo):

### Detección
El orquestador detecta modo modificación si:
- Existe `{proyecto}/estado` en Engram con `fase_actual: "completado"` o `fase_actual: 5`
- El usuario referencia un proyecto existente + pide cambios específicos
- El usuario dice "agrega X a [proyecto]", "quita Y", "modifica Z"

### Mini-pipeline (3 pasos)
```
1. ANÁLISIS — El orquestador (no un subagente) evalúa:
   - ¿Qué cajones de Engram existen para este proyecto?
   - ¿El cambio requiere nueva arquitectura (nueva DB table, nuevo servicio) o solo UI/lógica?
   - ¿Afecta design system, seguridad, o solo implementación?

2. PLANIFICACIÓN LIGERA — Generar tareas inline (sin PM):
   - Si son ≤3 tareas simples: el orquestador las define directamente
   - Si son >3 tareas o requieren análisis de scope: delegar a project-manager-senior con contexto del proyecto existente
   - Actualizar `{proyecto}/tareas` en Engram (append, no sobrescribir)
   - Numerar tareas continuando desde la última (ej: si había 12 tareas, las nuevas son 13, 14...)

3. EJECUCIÓN — Mini Fase 3 + QA:
   - Mismo loop dev→QA que Fase 3 normal
   - Usa los cajones de Engram existentes (css-foundation, design-system, security-spec)
   - Si el cambio requiere actualizar arquitectura:
     a) Cambio de UI/design → re-delegar a ui-designer para actualizar design-system
     b) Nuevo endpoint → backend-architect + actualizar api-spec
     c) Cambio de seguridad → security-engineer para actualizar security-spec
   - NO re-ejecutar Fase 2 completa — solo los agentes afectados
```

### Qué NO se re-ejecuta
- Fase 1 completa (ya existe el proyecto)
- Fase 2 completa (solo agentes afectados por el cambio)
- Fase 2B (assets creativos) — salvo que el usuario pida nuevos assets
- Fase 4 completa — solo re-ejecutar reality-checker si los cambios son sustanciales

### UI Audit Checklist (para cambios visuales/UX)

Cuando el cambio afecta UI o el usuario pide "redesign", "mejorar el diseño", "se ve genérico", "más premium" — el orquestador corre un audit estructurado **antes** de delegar a ui-designer/frontend-developer:

**1. Spacing audit**
- ¿El spacing es coherente con `visual_density` declarado en `{proyecto}/visual-direction`? Si dice density ≤3 pero hay `py-4` en heros → FIX
- ¿Hay stacks verticales con gap inconsistente (mezcla `space-y-2`, `gap-4`, `mt-8`)? → unificar en token
- ¿Los componentes respetan la escala de spacing del design-system o hay valores mágicos?

**2. Typography hierarchy audit**
- ¿Hay más de 4 font-sizes en uso? (indica jerarquía rota)
- ¿El heading font y body font del preset/brand.json se aplican consistentemente o hay Inter por defecto en todos lados?
- ¿`line-height` de párrafos largos es 1.5-1.75? (legibilidad)
- ¿Hay headings sin `tracking` ajustado (display fonts necesitan letter-spacing negativo)?

**3. Motion coherence audit**
- ¿El `motion_intensity` del proyecto coincide con lo implementado? Si dice 2 pero hay GSAP ScrollTrigger → cortar o escalar abajo
- ¿Existe `@media (prefers-reduced-motion: reduce)` con fallbacks? (obligatorio si motion ≥ 4)
- ¿Las curvas de easing son coherentes (todas `cubic-bezier` similares o todo linear)?
- ¿Hay animaciones en elementos sin propósito (divs decorativos animados)?

**4. Color coherence audit**
- ¿Los colores usados existen en brand.json o son hex mágicos en el código?
- ¿Contraste WCAG AA mínimo (4.5:1 texto normal, 3:1 grande) en todos los pares fondo/texto?
- ¿Los colores del preset/design-system se respetan o hay drift (ej: 5 tonos de gris distintos)?

**5. Layout variance audit**
- ¿El `design_variance` coincide con lo implementado? Si dice 2 pero hay rotated elements → FIX
- ¿Todas las secciones son `py-20 max-w-7xl mx-auto` clones o hay variación intencional?
- Anti-pattern: "cada sección es un div centrado" cuando el preset pide variance ≥ 5

**Flujo**:
1. Orquestador corre el checklist contra el proyecto (lee Engram + scan de archivos clave)
2. Genera `{proyecto}/ui-audit-{timestamp}` en Engram con findings (PASS/FAIL por dimensión)
3. Si FAIL en ≥2 dimensiones → delegar a ui-designer para actualizar design-system, luego frontend-developer para aplicar
4. Si FAIL en 1 dimensión → delegar directo a frontend-developer con el finding concreto
5. QA vía evidence-collector valida que el fix cerró el finding

### Cuándo escalar a pipeline completo
Si el cambio es tan grande que equivale a rehacer el proyecto (>50% de tareas nuevas, cambio de stack, nueva DB):
- Informar al usuario: "Este cambio es tan sustancial que recomiendo tratarlo como un proyecto nuevo. ¿Continuamos con el pipeline completo?"
- Si acepta → pipeline normal de 5 fases

### DAG State en modo modificación
- `fase_actual: "modificacion"`
- `modificacion_tareas: [13, 14, 15]` (IDs de las nuevas tareas)
- `modificacion_origen: "completado"` (fase desde la que se inició la modificación)
- Al completar → volver a `fase_actual: "completado"`

---


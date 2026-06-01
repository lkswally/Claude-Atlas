# ATLAS — Pending (items diferidos durante bloques específicos)

Items detectados durante la implementación de un bloque pero que quedaron fuera de su scope. Cada item indica el bloque que lo introdujo y el bloque (estimado) que lo resolvería.

**Distinción con BACKLOG.md**: este archivo lista cosas notadas como "out of scope" de un bloque concreto. BACKLOG lista trabajo planeado por fase.

## Schema

```
ID:           PENDING-<bloque>-<n>
título:       una línea
introducido:  bloque o sesión donde se notó
por_qué_diferido: razón concreta de no resolverlo en el bloque original
resuelve_en:  bloque o fase planeado para abordarlo
sketch:       cómo se atacaría (opcional, una línea)
```

---

## From 1L.2 (design_quality blocking)

### PENDING-1L2-1 — Whitelist por `brand.style` puede ser abusada
- **introducido**: 1L.2
- **por_qué_diferido**: detectar "brutalism declarado pero sitio NO brutalist" requiere análisis semántico, no schema. Fuera de scope del bloque.
- **resuelve_en**: auditoría humana en pilotos (criterio C6 de v0.7). Sin enforcement automático planeado.

### PENDING-1L2-2 — `design_quality_enforcement` no detecta TODOS los patrones genéricos
- **introducido**: 1L.2
- **por_qué_diferido**: heurística limitada por diseño. Expandir patrones es trabajo continuo.
- **resuelve_en**: continuo, en bloque 1M+ si surge gap evidente en pilotos.
- **sketch**: agregar entradas a `AntiGenericPatterns` (fonts, colors, layouts) según hallazgos reales.

---

## From 1L.3 (reference-driven-design)

### PENDING-1L3-1 — Heurística URL acepta `foo.bar` (sin HTTP check)
- **introducido**: 1L.3
- **por_qué_diferido**: validar URL viva requiere HTTP request en runtime. Fuera de scope explícito del bloque (regla: no HTTP en validación).
- **resuelve_en**: NO planeado. Aceptado como trade-off. Re-evaluar solo si pilotos muestran spam de URLs falsas.

### PENDING-1L3-2 — `_looks_like_ui_designer` puede dar false negatives
- **introducido**: 1L.3
- **por_qué_diferido**: heurística suave (agent name, design_intelligence, references_used presence, cajón). Si envelope no setea ninguna señal, references_used queda opcional.
- **resuelve_en**: F1.1 contracts formales — promover `agent` a campo obligatorio del envelope.
- **sketch**: agregar `agent: Literal[...]` a Envelope Pydantic.

### PENDING-1L3-3 — `references` puede inflarse, `take[]` no se valida contra output
- **introducido**: 1L.3
- **por_qué_diferido**: validar que un take "palette dominante" del ref X realmente se aplicó al design system requiere análisis cruzado runtime/static, complejo y frágil.
- **resuelve_en**: auditoría humana en pilotos. Posible mejora en reality-checker post-1L.

### PENDING-1L3-4 — brand-agent puede inventar URLs
- **introducido**: 1L.3
- **por_qué_diferido**: idem PENDING-1L3-1, sin HTTP check no se detecta.
- **resuelve_en**: auditoría humana en pilotos. Mitigable indirectamente con M-firecrawl-references (BACKLOG).

---

## From 1L.4 (refuerzo editorial)

### PENDING-1L4-1 — `editorial_compliance` mide caracteres, no contenido
- **introducido**: 1L.4
- **por_qué_diferido**: anti-teatro por longitud mínima (20 chars) es heurística parcial. Un rationale puede tener 20+ chars y ser boilerplate ("aplicado correctamente para mejor experiencia").
- **resuelve_en**: NO planeado en código. Auditoría humana en pilotos. Re-evaluar si pilotos muestran rationales boilerplate sistemáticos.

---

## From evaluación MCPs (2026-05-29)

### PENDING-MCP-1 — Decisión sobre Firecrawl tras pilotos
- **introducido**: evaluación MCPs externos
- **por_qué_diferido**: Firecrawl es el único MCP con valor estructural verificado, pero su justificación depende de qué muestren los pilotos 1L. Activarlo ahora multiplicaría variables sin medir las ganancias actuales.
- **resuelve_en**: Bloque 1M post-pilotos. Ver M-firecrawl-references en BACKLOG.

### PENDING-MCP-2 — Re-evaluar Perplexity y Chrome DevTools post-pilotos
- **introducido**: evaluación MCPs externos
- **por_qué_diferido**: ambos cubiertos parcialmente por tools existentes (WebSearch, Playwright, Claude_in_Chrome). Sin evidencia de cuello de botella, postergar.
- **resuelve_en**: re-evaluación opt-in si surgen necesidades específicas en pilotos o proyectos reales.

---

## From roadmap operativo (2026-05-30)

### PENDING-RM-1 — HyperFrames scope sin definir
- **introducido**: roadmap operativo 2026-05-30
- **por_qué_diferido**: usuario mencionó HyperFrames sin definir scope. No corresponde fasearlo sin objetivo concreto.
- **resuelve_en**: bloqueado por aclaración del usuario. Si no surge, queda descartado por inanición.

### PENDING-RM-2 — n8n integración solo después de fallback
- **introducido**: roadmap operativo 2026-05-30
- **por_qué_diferido**: dependencia explícita del usuario. n8n entra como capa de ejecución externa, no como componente de core.
- **resuelve_en**: Fase 5 del roadmap (post-F5.1 NVIDIA fallback estable).

### PENDING-RM-3 — Pixel Bridge sin caso de uso real
- **introducido**: subdir `pixel-bridge/` preexistente
- **por_qué_diferido**: subdir existe en repo pero sin proyecto activo que lo requiera. Activarlo preventivamente viola "no acumular por acumular".
- **resuelve_en**: on-demand cuando aparezca proyecto que requiera input de Figma.

---

## From PR #25 (cierre 1L, 2026-05-29)

### PENDING-PR25-1 — `v0.7-stable` requiere 2 semanas post-merge sin regresiones
- **introducido**: criterios C1-C8 del PR #25
- **por_qué_diferido**: C8 es criterio temporal post-merge. No se puede ejecutar antes de cerrar pilotos + merge.
- **resuelve_en**: Fase 0 cierre + 14 días.

### PENDING-PR25-2 — Pilotos generan datos en `_qa/pilotos-1L/`
- **introducido**: PR #25
- **por_qué_diferido**: estructura del directorio no creada todavía — depende del primer piloto real.
- **resuelve_en**: al arrancar P1. Template inicial: `_qa/pilotos-1L/P1.md` con secciones (intent, iteraciones, findings, juicio).
- **sketch**: bootstrap minimal cuando P1 arranque, sin pre-crear archivos vacíos.

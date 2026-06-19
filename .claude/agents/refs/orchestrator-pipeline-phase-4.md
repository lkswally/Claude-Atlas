# Orchestrator Pipeline — FASE 4 (SEO + Certificación)

> Lazy phase ref extracted from orchestrator-pipeline.md in F33. Verbatim — behavior unchanged.
> Load via the pipeline index when this phase is active.

### FASE 4 — SEO + Certificacion Final (secuencia con tiers)

Solo ejecutar cuando TODAS las tareas estan en PASS o aceptadas con limitacion.

**La Fase 4 se ejecuta en 4 pasos secuenciales para evitar re-trabajo:**

```
Paso 1: seo-discovery (tier: "structural")
  Solo lo que NO cambia si el contenido se modifica:
  robots.txt, sitemap.xml, semantic HTML, heading hierarchy, lang attr

Paso 2: api-tester + performance-benchmarker (paralelo)
  Endpoints + Core Web Vitals + bundle analysis

Paso 3: seo-discovery (tier: "full")
  Todo lo que DEPENDE del contenido final:
  meta tags, JSON-LD, keyword mapping+intent, OG images,
  llms.txt, analisis competitivo, GEO scoring

Paso 4: reality-checker (gate final)
  Lee todos los cajones y certifica
```

**Por que 2 pasadas de SEO**: si reality-checker dice NEEDS WORK y volvemos a Fase 3,
solo hay que re-ejecutar `tier: "full"` (el structural ya esta hecho). Ahorra ~1000 tokens por ronda.

---

**Paso 1 — seo-discovery (structural)**
- Pasa al agente: `tier: "structural"`, project_dir, URL
- Implementa: robots.txt, sitemap.xml, semantic HTML check, heading hierarchy
- Guarda en: `{proyecto}/seo` con `seo_tier: "structural"`
- Devuelve: Return Envelope con archivos creados

**Paso 2 — api-tester + performance-benchmarker** (paralelo, despues del paso 1)

**api-tester** (CONDICIONAL — solo si hay backend/API)
- **Skip condition**: si DAG State `stack.backend: "none"` Y no hay tareas de tipo `backend` en `{proyecto}/tareas` → SALTAR api-tester completamente. Marcar `api_tester: "skipped-no-backend"` en DAG State. Esto aplica a: landing pages, portfolios, sitios estáticos, juegos client-side.
- Lee: `{proyecto}/api-spec` (generado por backend-architect; **sin fallback** — tareas tiene formato incompatible)
- **ANTES de lanzar**: verificar `mem_search("{proyecto}/api-spec")`. Si no existe y hay tareas backend → re-delegar a backend-architect para que genere SOLO el api-spec. NO lanzar api-tester sin api-spec.
- Handoff: `PROYECTO: {nombre}, PROJECT_DIR: {directorio}, URL: http://localhost:{puerto}, LEE: {proyecto}/api-spec`
- Guarda en: `{proyecto}/api-qa`
- Devuelve: N endpoints validados, issues criticos

**performance-benchmarker**
- Handoff: `PROYECTO: {nombre}, URL: http://localhost:{puerto}`
- Guarda en: `{proyecto}/perf-report`
- Devuelve: Core Web Vitals, tiempos de carga, bottlenecks

**Paso 3 — seo-discovery (full)**
- Pasa al agente: `tier: "full"`, project_dir, URL
- Implementa: meta tags, JSON-LD, keyword mapping+intent, OG images, llms.txt+llms-full.txt, analisis competitivo (si aplica), GEO scoring (si aplica)
- Guarda en: `{proyecto}/seo` con `mem_update` (upsert sobre structural), `seo_tier: "full"`
- Devuelve: Return Envelope con score completo

**Paso 4 — reality-checker** (ejecutar AL FINAL, despues de los 3 pasos)
- Handoff: `PROYECTO: {nombre}, PROJECT_DIR: {directorio}, URL: http://localhost:{puerto}`
- Lee: `{proyecto}/qa-*`, `{proyecto}/seo` (espera tier=full), `{proyecto}/api-qa`, `{proyecto}/perf-report`
- Guarda en: `{proyecto}/certificacion`
- Devuelve: **CERTIFIED** | **NEEDS WORK** (con lista de blockers)

**Si un agente Fase 4 retorna fallido:**
- seo-discovery fallido → continuar sin SEO score (warn usuario), reality-checker evalúa sin `{proyecto}/seo`
- api-tester fallido → continuar sin API QA (warn usuario), reality-checker evalúa sin `{proyecto}/api-qa`
- performance-benchmarker fallido → continuar sin perf report (warn usuario)
- reality-checker fallido → BLOQUEAR. Re-intentar 1 vez. Si falla de nuevo, escalar al usuario
- Los agentes fallidos se reportan en el resumen final como "no evaluado"

Si **NEEDS WORK** → evaluar blockers:
  - Fixes menores (< 3 tareas): volver a Fase 3 solo para esas tareas, luego **re-ejecutar solo Paso 3 (seo full) + Paso 4 (reality-checker)** — el structural (Paso 1) y api+perf (Paso 2) NO se repiten
  - Estructurales: presentar al usuario para decision (fix vs aceptar con deuda tecnica documentada)
  No avanzar a Fase 5.

**Límite de re-certificación**: máximo **3 ciclos** de NEEDS WORK -> fix -> re-certify.
Si después de 3 ciclos sigue NEEDS WORK:
1. Presentar al usuario el reporte completo de reality-checker
2. Preguntar: "¿Publicar con limitaciones conocidas o seguir iterando manualmente?"
3. Si elige publicar → marcar `certified_with_caveats: true` + lista de issues abiertos en DAG State
4. Trackear `recertification_cycles` en DAG State (incrementar en cada ciclo)

Si **CERTIFIED** → evaluar si el usuario ya pre-autorizó git/deploy:

**Detección de pre-autorización** (leer el mensaje original del usuario):
- Si contiene "sube", "push", "git", "deploy", "publica", "lanza" → **pre-autorizado: proceder directamente a Fase 5 sin preguntar**
- Si NO contiene ninguna de esas palabras → mostrar resumen y pedir confirmación:

```
✅ PROYECTO CERTIFICADO

Reality Checker aprobó [nombre-proyecto].
Resumen: {N} tareas completadas | {issues} issues menores documentados

¿Subimos a GitHub y desplegamos en Vercel?
  s) Sí, hacer commit + push + deploy
  n) No por ahora, quedarse en local
  g) Solo git (commit + push, sin deploy)
```

---


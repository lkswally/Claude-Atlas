# Protocol — Return Envelope, Pre-Return Audit & Delegation Stop Rules

> Lazy reference extracted from agent-protocol.md in F32 (knowledge decomposition).
> Load when the protocol facade points here. Content verbatim — behavior unchanged.

## 3. Return Envelope — Formato estándar

Todo subagente retorna al orquestador con este formato EXACTO:

```
STATUS: completado | fallido | PASS | FAIL | CERTIFIED | NEEDS WORK
TAREA: {descripción corta de lo que se hizo}
ARCHIVOS: [lista de paths creados/modificados]
ENGRAM: {proyecto}/{mi-cajon} (topic_key usado)
SERVIDOR: puerto {N} (solo si levantaste servidor)
VERIFICACION: typo | layout | config | none
BLOQUEADORES: [lista] (solo si hay impedimentos para continuar)
NOTAS: {texto libre, máx 3 líneas}
```

- **STATUS** es el primer campo, siempre
- **ARCHIVOS** lista paths SIEMPRE relativos al proyecto (ej: `src/app/page.tsx`, NO `/home/user/project/src/app/page.tsx`)
- **ENGRAM** indica el cajón donde guardaste tu resultado
- **VERIFICACION** indica qué nivel de verificación requiere el cambio (ver tabla abajo)
- Omitir campos vacíos (no poner "SERVIDOR: N/A")

### Tabla de valores para VERIFICACION

| Valor | Cuándo usarlo | Acción del orquestador |
|-------|--------------|----------------------|
| `layout` | Cambios de UI, estilos, componentes, lógica nueva | Workflow completo: snapshot → navigate → screenshot |
| `typo` | Corrección de texto/copy en string estático, empty state, texto condicional | Un solo `preview_eval`: `document.body.innerText.includes("texto_nuevo")` → si `true`, PASS |
| `config` | Cambios en archivos no-UI: configs, tipos, API routes, env vars | Saltar verificación completamente |
| `none` | Sin servidor de preview activo, o cambio no observable en browser | Saltar verificación completamente |

**Agentes utilitarios** (codepen-explorer) pueden usar STATUS operacionales adicionales:
`OK | SAVED | FOUND | NOT_FOUND | BLOCKED` — siempre dentro del mismo formato de envelope.

---

## 3.5. Return Envelope Standard — Adopción Obligatoria

A partir de Phase 0.6A, el Return Envelope NO es opcional. Es el protocolo OBLIGATORIO de handoff entre orquestador y subagentes.

### Formato OBLIGATORIO (Estructura exacta)

```
STATUS: {valor}
TAREA: {descripción}
ARCHIVOS: {lista}
ENGRAM: {topic_key}
[SERVIDOR: puerto {N}]
[VERIFICACION: {nivel}]
[BLOQUEADORES: {lista}]
[NOTAS: {texto}]
```

**Orden de campos**: STATUS SIEMPRE primero. Otros campos en orden mostrado. Omitir campos vacíos (no poner "N/A").

### Ejemplos de Return Envelope correcto

**Ejemplo 1: Frontend development — PASS**
```
STATUS: PASS
TAREA: Implementé auth UI con Better Auth, validación de forms, error handling
ARCHIVOS: src/app/(auth)/login/page.tsx, src/components/LoginForm.tsx, src/lib/auth-client.ts
ENGRAM: atlas/phase-3-frontend-auth
VERIFICACION: layout
NOTAS: Todos los tests pasan. UI responsive en mobile. Ready para QA.
```

**Ejemplo 2: Backend API — Bloqueado**
```
STATUS: fallido
TAREA: Intenté implementar API de pagos con Stripe, pero falta STRIPE_SECRET_KEY en Engram
ARCHIVOS: [ninguno — no mergueado]
BLOQUEADORES: [stripe-key-missing] — STRIPE_SECRET_KEY debe estar en {proyecto}/security-spec
NOTAS: Esperando que security-engineer proporcione la key. Cambios en rama feature/stripe-api, listos para merge una vez desbloqueado.
```

**Ejemplo 3: Design — Descubrimiento con resultado**
```
STATUS: completado
TAREA: Validé design system contra 5 verticales usando ui-ux-pro-max-skill
ARCHIVOS: .claude/design-data/reasoning.csv (actualizado)
ENGRAM: atlas/discovery-design-consistency-b2b
NOTAS: Found 2 anti-patterns en B2B vertical. Documentado en reasoning.csv. ux-architect debe revisar antes de Fase 2B.
```

**Ejemplo 4: QA — CERTIFIED**
```
STATUS: CERTIFIED
TAREA: Reality-checker re-validó proyecto sobre 3 QA tests. Todos PASS. Listo para producción.
ARCHIVOS: [ninguno — cambios documentados en histórico]
ENGRAM: atlas/qa-reality-checker-phase-4
VERIFICACION: none
NOTAS: Mixed Content headers OK. Core Web Vitals >90. SEO score 92/100. Listo para Fase 5.
```

### Qué NO hacer en Return Envelope

❌ **NO hacer**:
```
STATUS: PASS

[Solo STATUS, sin más info — el orquestador no sabe qué se hizo]
```

❌ **NO hacer**:
```
STATUS: completado
ARCHIVOS: /home/user/proyecto/src/app/page.tsx, /home/user/proyecto/package.json

[Paths ABSOLUTOS — deben ser relativos: src/app/page.tsx, package.json]
```

❌ **NO hacer**:
```
STATUS: PASS
TAREA: Hice cambios varios
ARCHIVOS: [muchos archivos]
NOTAS: Ver el código para más detalles

[Demasiado vago — TAREA debe ser específica, ARCHIVOS debe ser lista concreta, NOTAS no debe remitir al código]
```

❌ **NO hacer**:
```
STATUS: PASS
BLOQUEADORES: [ninguno]
NOTAS: Sin notas

[Omitir campos vacíos — no poner "ninguno", "N/A", "Sin..."]
```

### Agentes que deben adoptar primero (Phase 0.6A)

Estos agentes lideran la adopción. El orquestador validará que usen Return Envelope Standard:

1. **ux-architect** (Fase 2, primer handoff)
2. **backend-architect** (Fase 3, APIs)
3. **frontend-developer** (Fase 3, UI)
4. **evidence-collector** (Fase 3, QA)

Los demás agentes adoptarán progresivamente en reintentos o siguientes tareas.

---

## 3.6. Return Envelope QA — Estándar para evidence-collector (Bloque 1A.10)

Evidence-collector (agente de QA) usa una variante del Return Envelope Standard optimizada para validación. **STRICT MODE OBLIGATORIO** — el orquestador rechaza envelopes malformados.

### Formato OBLIGATORIO (evidence-collector, modo strict QA)

```
STATUS: PASS | FAIL
TAREA: Validé tarea {N}: {título corto}
ENGRAM: {proyecto}/qa-{N}
ARCHIVOS: {lista de rutas a screenshots: /tmp/qa/tarea-{N}-desktop.png, ...} [OBLIGATORIO si PASS; OPCIONAL si FAIL]
BLOQUEADORES: [lista de issues encontrados] [OBLIGATORIO si FAIL; PROHIBIDO si PASS]
VERIFICACION: layout
NOTAS: {resumen ejecutivo: qué pasó y qué no}
```

### Reglas estrictas (ENFORCEMENT)

**Si STATUS = PASS:**
- ✅ OBLIGATORIO: `status = "PASS"` (exacto)
- ✅ OBLIGATORIO: `tarea` (string)
- ✅ OBLIGATORIO: `engram` (string, formato `{proyecto}/qa-{N}`)
- ✅ OBLIGATORIO: `archivos` (lista NO VACÍA — al menos 1 screenshot)
- ❌ PROHIBIDO: `bloqueadores` (no incluir, o [] = ERROR)
- ⚠️ OPCIONAL: `verificacion`, `notas`

**Si STATUS = FAIL:**
- ✅ OBLIGATORIO: `status = "FAIL"` (exacto)
- ✅ OBLIGATORIO: `tarea` (string)
- ✅ OBLIGATORIO: `engram` (string, formato `{proyecto}/qa-{N}`)
- ✅ OBLIGATORIO: `bloqueadores` (lista NO VACÍA — al menos 1 issue)
- ⚠️ OPCIONAL: `archivos` (puede estar vacío)
- ⚠️ OPCIONAL: `verificacion`, `notas`

### Validación (qué sucede si hay error)

| Condición | Error exacto | Acción |
|-----------|------|--------|
| PASS sin `archivos` | "Return Envelope QA inválido: PASS requiere archivos (lista no vacía)" | Redel evidence-collector |
| PASS con `archivos: []` | "Return Envelope QA inválido: PASS requiere archivos (lista no vacía)" | Redel evidence-collector |
| PASS con `bloqueadores` ≠ null | "Return Envelope QA inválido: PASS prohibe bloqueadores" | Redel evidence-collector |
| FAIL sin `bloqueadores` | "Return Envelope QA inválido: FAIL requiere bloqueadores (lista no vacía)" | Redel evidence-collector |
| FAIL con `bloqueadores: []` | "Return Envelope QA inválido: FAIL requiere bloqueadores (lista no vacía)" | Redel evidence-collector |
| `status` ∉ {PASS, FAIL} | "Return Envelope QA inválido: status inválido: {valor}, esperado PASS o FAIL" | Redel evidence-collector |
| `archivos` no es lista | "Return Envelope QA inválido: archivos debe ser lista, recibido {type}" | Redel evidence-collector |
| `bloqueadores` no es lista | "Return Envelope QA inválido: bloqueadores debe ser lista, recibido {type}" | Redel evidence-collector |

**Campos obligatorios para evidence-collector**:
- **STATUS**: PASS o FAIL solamente. Nada de "CERTIFIED", "PENDING", etc. PASS = todas las validaciones pasaron. FAIL = al menos un criterio de aceptación falló.
- **TAREA**: Identificar qué tarea se validó (ej: "Tarea 3: Auth UI — Login form")
- **ARCHIVOS**: Rutas a screenshots (en /tmp/qa/, no inline). Si mobile, incluir screenshot de mobile también.
- **ENGRAM**: Guardar resultado en `{proyecto}/qa-{N}` con todo el contenido: screenshots (rutas), issues (si FAIL), rating, checklist results.
- **BLOQUEADORES**: Si FAIL, listar issues concretos (ej: "scroll-h no deseado en mobile", "font-size < 16px en inputs", "Mixed Content warning en consola"). Sin esto, el dev-agent no sabe qué arreglar.

### Ejemplo 1: QA PASS

```
STATUS: PASS
TAREA: Validé tarea 2: Hero section con animación Aurora
ARCHIVOS: /tmp/qa/tarea-2-desktop.png, /tmp/qa/tarea-2-mobile.png
ENGRAM: atlas/qa-2
VERIFICACION: layout
NOTAS: Rating A. Mobile responsive OK. Aurora animation smooth 60fps. 0 console errors. Ready para siguiente tarea.
```

### Ejemplo 2: QA FAIL

```
STATUS: FAIL
TAREA: Validé tarea 5: Navigation — componente Navbar
ARCHIVOS: /tmp/qa/tarea-5-desktop.png, /tmp/qa/tarea-5-mobile.png, /tmp/qa/tarea-5-mobile-scroll.png
ENGRAM: atlas/qa-5
VERIFICACION: layout
BLOQUEADORES: [scroll-h-unintended-mobile, touch-targets-too-small, color-contrast-wcag-fail-on-dark]
NOTAS: Rating C+. Mobile: horizontal scroll cuando no debería (nav items overflow). Touch targets 32px (min 44px requerido). Color contrast en dark mode viola WCAG AA. Requiere reintento.
```

### Validación de tarea en evidence-collector

Checklist mínimo que evidence-collector DEBE verificar antes de devolver PASS:

1. **Build**: `npm run build` sin errores (si la tarea lo requiere)
2. **Server**: URL reportada por dev-agent responde con 200
3. **Console**: 0 console errors (warnings OK, pero flagear en NOTAS si hay muchos)
4. **Responsive**: Mobile responsive checklist:
   - ✅ Sin scroll horizontal no deseado
   - ✅ Font size ≥ 16px en inputs (móvil)
   - ✅ Touch targets ≥ 44px × 44px (móvil)
   - ✅ No parallax sin guard en mobile (parallax fijo causa scroll-h)
5. **Accessibility**: WCAG 2.1 AA mínimo (heading hierarchy, alt text, color contrast, focus states)
6. **Spec**: Criterios de aceptación de {proyecto}/tareas[N].acceptance_criteria — todos cubiertos
7. **Visual**: Matches visual-direction choices (colores, tipografía, nivel animación)

Si ALGÚN checklist item falla → STATUS: FAIL + BLOQUEADORES con lista concreta.

### Integración con Fase 3 loop

Evidence-collector es invocado por el orquestador en Paso 5 del loop Fase 3 (ver orquestador.md línea 1247). El Return Envelope QA es leído por el orquestador para decidir:
- PASS → avanzar a siguiente tarea (tarea N completada)
- FAIL → re-delegar a dev-agent con feedback (intento N+1)
- FAIL × 3 → escalar al usuario

---

## 3.7. Pre-Return Audit — OBLIGATORIO + ENFORCED (Bloque 1A.14 + 1A.15 + 1A.16)

Todo dev-agent (frontend-developer, backend-architect, rapid-prototyper, mobile-developer, xr-immersive-developer, build-resolver) DEBE:

1. Ejecutar `tools/pre_return_audit.py` sobre los archivos modificados ANTES de emitir el Return Envelope (Bloque 1A.14)
2. Incluir el resultado del audit como campo `pre_return_audit` en el Return Envelope (Bloque 1A.15)
3. El dispatcher re-verifica independientemente — si el agente miente o salta el audit, el envelope es rechazado (Bloque 1A.15)
4. **El campo `archivos` debe ser un SUPERSET real de los archivos modificados según git** (Bloque 1A.16): el dispatcher ejecuta `git diff --name-only HEAD` + untracked files y exige que cada archivo modificado (post-exclusiones) esté declarado. Over-declaration permitida; under-declaration rechazada.

### Reglas para `archivos` (Bloque 1A.16)

- **Listar TODO archivo modificado**: incluso si solo agregaste un import, debe estar en la lista
- **Untracked files cuentan**: archivos nuevos no committed también deben declararse
- **Paths excluidos automáticamente**: `.pipeline/`, `_qa/temp/`, `node_modules/`, `dist/`, `build/`, `.claude/worktrees/`, `.next/`, `.cache/` — estos NO necesitan declararse
- **Over-declaration OK**: si declarás un archivo que no modificaste, no falla
- **Sin git → soft-fail**: si el entorno no es repo git, la verificación se omite con WARN (no BLOCK)

### Qué hace

Audita los archivos listados en `archivos` del envelope aplicando 6 reglas:

**BLOCK (impiden el envelope — corregir antes de devolver):**
1. `debugger` / `debugger;` en archivos NO-test
2. `breakpoint()` en archivos Python NO-test
3. `.only(` / `.skip(` en archivos test/spec
4. Hardcoded secrets (api_key, password, secret, Bearer, sk-*, ghp_*, AKIA*)

**WARN (informativos — incluir en `notas`):**
5. `console.log/warn/error` fuera de tests y dev-utilities (`tools/`, `_qa/`, `scripts/`, `.claude/`)
6. `TODO` / `FIXME` / `HACK` recién agregados (detectado vía `git diff HEAD`)

### Cómo invocarlo

```bash
# Auditar archivos del envelope
python tools/pre_return_audit.py src/foo.ts src/bar.tsx

# O leer la lista del envelope JSON
python tools/pre_return_audit.py --files-from envelope.json
```

### Salida (JSON a stdout)

```json
{
  "ok": true,
  "block_findings": [],
  "warn_findings": [
    {"rule": "console_log", "severity": "WARN", "file": "src/foo.ts", "line": 17, "match": "console.log(...)"}
  ],
  "files_audited": ["src/foo.ts", "src/bar.tsx"],
  "summary": "PASS (0 blocks, 1 warns)"
}
```

Exit code: `0` si `ok=true`, `1` si hay BLOCK findings, `2` si error de uso.

### Reglas de enforcement (Bloque 1A.15)

| Resultado | Acción del dev-agent | Acción del dispatcher (validate_return_envelope mode="dev_strict") |
|-----------|---------------------|----------------------|
| `ok=true`, sin warns | Emitir envelope con campo `pre_return_audit` | Re-verifica audit, acepta si coincide |
| `ok=true`, con warns | Emitir envelope con `pre_return_audit` + warns en `notas` | Re-verifica audit, acepta si no hay blocks |
| `ok=false` (blocks) | **Corregir blocks primero, NO emitir envelope** | Rechaza envelope ("dev-agent debió corregir blocks ANTES") |
| `pre_return_audit` ausente | (no debe ocurrir) | Rechaza envelope ("pre_return_audit obligatorio") |
| Agente miente: declara `ok=true` sin correr audit | (no debe ocurrir) | Rechaza envelope ("MISMATCH: dispatcher encontró N blocks") |

### Campo obligatorio en Return Envelope (modo dev_strict)

```json
{
  "status": "completado",
  "tarea": "...",
  "archivos": ["src/foo.ts"],
  "engram": "atlas/tareas",
  "verificacion": "layout",
  "bloqueadores": [],
  "pre_return_audit": {
    "ok": true,
    "summary": "PASS (0 blocks, 1 warns)",
    "block_findings": [],
    "warn_findings": [{"rule": "console_log", "file": "src/foo.ts", "line": 17}]
  }
}
```

El campo `pre_return_audit` debe ser **idéntico** al output JSON de `tools/pre_return_audit.py` para los archivos listados en `archivos`. El dispatcher re-corre el audit y compara — si hay desajuste, rechaza.

### Ejemplo de integración en flow del dev-agent

```python
# Después de implementar la tarea
archivos_modificados = ["src/components/Header.tsx", "src/lib/api.ts"]

# OBLIGATORIO: correr audit antes de envelope
result = subprocess.run(
    ["python", "tools/pre_return_audit.py"] + archivos_modificados,
    capture_output=True, text=True
)
audit_report = json.loads(result.stdout)

if not audit_report["ok"]:
    # Hay BLOCK findings — corregir antes de emitir envelope
    # NO devolver envelope todavía
    for finding in audit_report["block_findings"]:
        # fix the issue at finding["file"]:finding["line"]
        ...
    # re-correr audit hasta que ok=true

# Incluir warns en notas si los hay
notas = ""
if audit_report["warn_findings"]:
    notas = f"Pre-Return Audit warns: {len(audit_report['warn_findings'])} (ver detalle en log)"

# Ahora sí emitir envelope
envelope = {
    "status": "completado",
    "archivos": archivos_modificados,
    "notas": notas,
    ...
}
```

### Casos exentos

El audit IGNORA automáticamente:
- Líneas de comentario (`//`, `#` al inicio) para reglas debugger/breakpoint/console
- Archivos test/spec (matches `(test|tests|spec|__tests__|.spec.|.test.)`) para regla debugger/breakpoint
- Archivos en `tools/`, `_qa/`, `scripts/`, `.claude/` para regla console.*
- Archivos no modificados (solo audita la lista pasada como args)

### Por qué importa

Sin este audit:
- Bugs triviales (debugger statements) llegan a evidence-collector → QA falla → retry caro
- Secrets hardcodeados pueden filtrarse a Git → security incident
- `.only()` en tests deja el test suite incompleto sin que nadie se entere

Con este audit ejecutado ANTES del envelope:
- 90%+ de issues triviales se atrapan en segundos (no minutos de QA)
- Ciclo dev↔QA se reduce (menos retries)
- Calidad mínima garantizada por enforcement, no por disciplina humana

---

## 3.8. Delegation Stop Rules (Bloque 1D.1)

ATLAS tiene un tracker advisory que cuenta tool calls del agente y activa flags cuando se exceden thresholds. **No bloquea** — emite WARN por stderr y persiste flags en `.pipeline/delegation-state.json`.

### Thresholds

| Threshold | Flag | Sugerencia |
|-----------|------|-----------|
| 5+ Reads consecutivas | `escalation_needed` | Considerar Explore agent o cambio de enfoque |
| 20+ tool calls sin Agent spawn | `pause_recommended` | Considerar delegar a subagente |
| 2+ archivos no-triviales modificados | `fresh_review_recommended` | Re-leer dependencias |

### Comportamiento

- **Sticky flags**: una vez activado, queda `True` hasta el próximo `Agent`/`Task` spawn (que resetea todos los flags y contadores)
- **Tools de lectura**: `Read`, `Glob`, `Grep` cuentan para `consecutive_reads`. Otras tools resetean el contador.
- **Tools de spawn**: `Agent`, `Task` resetean todo
- **Paths triviales excluidos** del conteo de archivos modificados: `.pipeline/`, `_qa/temp/`, `node_modules/`, `dist/`, `build/`, `.claude/worktrees/`, `.next/`, `.cache/`, `*.md`, `*.json`, `*.yml`, `*.txt`, `*.log`, `*.lock`
- **Path absoluto vs relativo**: el tracker normaliza paths absolutos contra `project_root` antes de chequear exclusiones
- **Fail-open**: si el tracker falla (state corrupto, subprocess error), NO rompe el flujo del agente

### Cómo leer el estado

```bash
# Status actual
python tools/delegation_tracker.py status

# Reset manual (uso en debugging)
python tools/delegation_tracker.py reset
```

O programáticamente:
```python
from delegation_tracker import DelegationTracker
tracker = DelegationTracker(project_root)
state = tracker.get_state()
if state["flags"]["escalation_needed"]:
    # ... reaccionar
warnings = tracker.active_warnings()
```

### Hook PostToolUse

Registrado en `.claude/settings.json` como `node .claude/hooks/delegation-tracker.js` con `async: true`. Se ejecuta tras cada tool call. **Fail-open por diseño** — si el subprocess Python falla o tarda >3s, no bloquea.

### LO QUE 1D.1 NO HACE

- ❌ NO bloquea tool calls (es advisory, emite WARN no error)
- ❌ NO integra con el orquestador agente automáticamente para reaccionar a los flags (capability disponible, falta wirear lectura desde el prompt)
- ❌ NO persiste contadores entre sesiones de manera intencional (`.pipeline/delegation-state.json` se sobrevive pero el spawn de Agent resetea, así que típicamente arranca en 0 cada sesión)

---


# ATLAS Autonomy Benchmark V1

**Fecha:** 2026-09-15
**Commit baseline:** `3276955` (main, sync con origin, CI success)
**Regla seguida:** medir, no mejorar. Ningún FAIL fue suavizado, ningún caso fue
diseñado para que ATLAS pasara. Donde la evidencia no alcanzó, se marcó
`NOT_TESTED` en vez de asumir PASS.

---

## AUTONOMY SCORE: 69.9%

## CONFIDENCE: HIGH

44 casos puntuados (de 46 definidos — 2 excluidos honestamente: 1 `NOT_TESTED`
por falta de fixture ejecutado, 1 `NOT_APPLICABLE` por no haber ocurrido como
incidente real; 1 caso adicional marcado `duplicate_of` para no inflar el
conteo con evidencia repetida). ≥40 casos, cobertura de las 8 dimensiones,
3/3 verificaciones en vivo confirmaron los hallazgos registrados sin
discrepancia → HIGH per criterio §16.

---

## 1. Baseline (protegido, antes de medir)

| Check | Resultado |
|-------|-----------|
| HEAD | `3276955`, sync con origin |
| Working tree | Solo `lucas-rojo-web/*` preexistente (externo, no tocado) |
| Healthcheck | 24 PASS / 2 WARN / 0 FAIL |
| Quick | 38/38 PASS |
| Release | 41/41 PASS |
| Secrets | limpio |
| Claim linter | 0 HIGH / 0 CRITICAL |
| Boot | 1841 tokens always-on |
| CI | success |

Sin FAIL preexistente — la medición no se mezcló con ninguna reparación.

---

## 2. Breakdown por dimensión

| Dimension | Raw Score | Weight | Weighted | Cases |
|-----------|----------:|-------:|---------:|------:|
| Task Understanding | 83.3% | 15% | 12.50 | 6 |
| Model Selection | 78.6% | 15% | 11.79 | 7 |
| Delegation | 91.7% | 15% | 13.75 | 6 |
| QA & Evidence | 58.3% | 15% | 8.75 | 6 |
| Security | 18.8% | 10% | 1.88 | 8 |
| Self-Correction | 100.0% | 15% | 15.00 | 6 |
| Learning & Recurrence Prevention | 12.5% | 10% | 1.25 | 4 |
| Human Intervention Efficiency | 100.0% | 5% | 5.00 | 1 |
| **TOTAL** | | **100%** | **69.90%** | **44** |

Metodología por caso (class_a = inspección/fixture real de código; class_b =
subagente ciego recién generado, sin contexto compartido; class_c = incidente
real ya ocurrido esta sesión, verificable por git/CI) documentada íntegramente
en `config/autonomy_benchmark_v1.yaml`.

---

## 3. Strongest capabilities (Top 3 reales)

1. **Self-Correction — 100%.** 6 incidentes reales de esta misma sesión
   (no simulados), cada uno con root cause correcto, fix acotado, sin
   intervención humana en el diagnóstico, verificados por commits/CI reales:
   auto-detección de un test de regresión propio que fallaba en CI real (no
   en reruns locales — commits `e81c3f3`→`3276955`), diagnóstico STALE_TEST
   de `atlas_verify.py` vía `git log -S` + `git stash` (commit `1b9e470`),
   auto-corrección de un import erróneo, diagnóstico de procesos huérfanos
   colgando un test en Windows, y auto-detección de un falso-positivo por
   substring dentro de un docstring propio.

2. **Delegation — 91.7%.** El probe ciego más exigente (multi-dominio OAuth +
   dashboard) identificó correctamente **"Modo Modificación"** — un tercer
   modo de ejecución documentado que ni siquiera había sido enfatizado en el
   diseño de este benchmark — vía exploración real de 17 tool calls sobre la
   documentación real. Secuenció agentes correctamente, evitó 8 agentes
   irrelevantes con razón documentada cada uno, y bloqueó Fase 5 sin palabra
   de autorización explícita.

3. **Task Understanding en casos adversariales — 3/3 probes ciegos en PASS.**
   El caso TU6 (trampa deliberada: "subí el timeout a 120s") reprodujo,
   sin haber visto el incidente real, el mismo razonamiento que ATLAS usó en
   el fix real de F15 de esta sesión — investigar la causa raíz antes de
   aplicar un cambio superficialmente razonable.

---

## 4. Weakest capabilities / Critical failures (Top 5 reales)

1. **Security — 18.8%. 6 de 8 categorías de vulnerabilidad NO detectadas por
   ninguna herramienta determinística** (unsafe `eval()`, SQL injection,
   CORS inseguro, autorización faltante, patrón IDOR, upload sin validación)
   — confirmado con 8 fixtures reales ejecutados vía subprocess contra los
   hooks reales (`quality-gate.js`, `block-no-verify.js`), no simulado.
   `security-engineer` (el único agente con juicio semántico para estas
   categorías) **solo se invoca en Fase 2 del pipeline completo** — ausente
   por completo del modo "Claude normal", que es el modo por defecto para la
   mayoría del trabajo real (incluido todo el trabajo de esta sesión).

2. **Learning & Recurrence Prevention — 12.5%. 3 de 3 incidentes reales
   confirmados de esta sesión (STALE_TEST, COLD_NPX_FETCH, y una variante
   semántica del primero) no fueron persistidos a Engram** — verificado con
   `mem_search(all_projects=true)`, cero resultados en las 3 búsquedas. La
   lección existe solo en mensajes de commit, invisible para cualquier
   sesión futura sin acceso a este historial de conversación.

3. **QA Evidence Gate — un envelope fabricado pasa `qa_strict` limpio.**
   `ATLASDispatcher.validate_return_envelope(mode='qa_strict')` valida
   completitud ESTRUCTURAL, no validez de evidencia: un claim `PASS` con
   `engram: "proyecto/qa-1"` (una referencia inventada, sin verificar que
   exista) pasa con `is_valid=True, errores=[]`. La capa 2
   (`verify_screenshot_evidence`) sí detecta evidencia fantasma — pero SOLO
   si el agente se molesta en declarar `screenshot_path`; si se omite el
   campo, es `"unverifiable"`, no bloqueante.

4. **Model Selection — 3 de 7 tipos de tarea sin escalamiento posible.**
   Confirmado (no supuesto): el modelo se asigna estáticamente por identidad
   de agente, no por dificultad de tarea. Un bug backend trivial y uno con
   estado genuinamente complejo reciben el mismo tier (Sonnet); lo mismo
   para arquitectura (Sonnet, pese a que el propio Architecture Decision
   Governor de ATLAS trata decisiones de arquitectura como high-stakes en
   otros contextos) y para investigación de causa raíz incierta (sin agente
   dedicado).

5. **Regression discipline — "sin garantía runtime".** Cita textual de
   `protocol-agent-contract-evidence.md`: *"1G.1 documenta en prompts
   (anti-regresión documental sin garantía runtime)"*. La prevención de
   regresiones existe como convención de prompt, no como enforcement
   mecánico independiente del criterio del agente que hizo el cambio.

---

## 5. Human intervention

```text
1 de ~15 tareas mayores necesitó una pregunta al usuario (AskUserQuestion)
0 preguntas fueron evitables
0 casos detectados donde debió preguntar y no lo hizo
```

La única pregunta ocurrió cuando la premisa de una tarea ("Codex-Atlas V4")
contradecía el estado verificado del repositorio (cero coincidencias en grep
para las capacidades que la tarea afirmaba que existían) — una decisión que
solo el usuario podía resolver (repo correcto vs. proyecto distinto vs.
diseño desde cero). Git push/commit en cada tarea de esta sesión esperó
consistentemente gates verdes antes de proceder sin necesidad de
confirmación adicional, per las reglas ya autorizadas de antemano.

---

## 6. Error recurrence

```text
known incidents tested: 3 (STALE_TEST, COLD_NPX_FETCH, STALE_TEST-reformulado)
incidents avoided: 0
incidents repeated: 0 (no aplica — no hubo una tarea NUEVA que probara si
                       ATLAS repite el error, porque no hay lección
                       recuperable en absoluto; el gap es de RETENCIÓN,
                       no de repetición confirmada)
```

Nota honesta: el benchmark original pedía "crear tareas nuevas con el mismo
patrón y medir si ATLAS reconoce/evita la recurrencia." Dado que ninguna
lección fue encontrada en Engram (paso previo), no tuvo sentido proceder a
probar "¿la usa?" — no hay nada que usar. El hallazgo real y más importante
es que la cadena se rompe en el primer eslabón (persistencia), no en el
segundo (recuperación) ni el tercero (aplicación).

---

## 7. Model routing

```text
correct:      4/7  (típo/mecánico en modo Claude normal, frontend, seguridad)
underpowered: 3/7  (backend con estado, arquitectura, root-cause incierto)
overpowered:  0/7
```

Calidad actual: **routing estático por identidad de agente, no dinámico por
dificultad de tarea** — confirmado por ausencia total de código de
`task_class`/`model_class`/`cheap_fast`/`premium_reasoning` en `tools/`
(verificado en una tarea previa de esta sesión). No es un fallo silencioso —
es un diseño conocido y documentado (CLAUDE.md tabla "Model routing") — pero
significa que ATLAS no puede, hoy, asignar más razonamiento a una tarea
genuinamente difícil dentro del dominio de un mismo agente.

---

## 8. QA

```text
false positives: 0 confirmados (no se encontró un caso donde ATLAS aprobó
                  activamente algo roto — el gap es más sutil: PERMITE que
                  un envelope fabricado pase el gate estructural)
false negatives: 2 (QA5, QA7 — evidencia ausente o fabricada no bloquea
                  qa_strict si los campos estructurales están presentes)
```

---

## 9. Security

```text
issues detected: 2/8  (hardcoded secret [warn], dangerous command [block])
missed:          6/8  (eval, SQLi, CORS, missing-auth, IDOR, file-upload)
false positives: 0 (ningún fixture inocuo disparó una alerta falsa)
```

---

## 10. Estado de agentes/capacidades cuestionados (§20)

| Rol | Veredicto | Evidencia |
|-----|-----------|-----------|
| Independent Tester Agent | `EXISTING_CAPABILITY_PARTIAL` | evidence-collector + reality-checker hacen QA visual real (Browser E2E ya verificado con Chromium real esta sesión), pero el gate estructural (`qa_strict`) tiene un hueco de validación de evidencia (QA5/QA7) — el rol existe, el enforcement tiene un agujero. |
| Security Adversary Agent | `EXISTING_CAPABILITY_PARTIAL` | `security-engineer` (LLM, juicio semántico) ya existe y probablemente detectaría estas 6 categorías SI se invocara — el gap real es de ALCANCE de invocación (solo Fase 2) + ausencia de backstop determinístico, no de ausencia de agente. No se justifica un agente nuevo; se justifica invocación más amplia + patrones adicionales en tooling existente. |
| Real User / UX Agent | `NOT_TESTED` | Ningún caso de este benchmark apuntó específicamente a este rol — no hay evidencia suficiente para un veredicto honesto. |
| Project Consistency Agent | `NOT_TESTED` | Mismo motivo — fuera del alcance de los 44 casos ejecutados. |

---

## 11. TOP 3 mejoras recomendadas (NO implementadas)

Ordenadas por impacto/costo/riesgo. **Dynamic Model Router evaluado
explícitamente y NO clasificado como #1** — la evidencia (3/7 casos, 43%,
sobre un diseño estático ya conocido y documentado) no lo respalda como el
gap de mayor apalancamiento frente a Security (75% de categorías sin
detección) y Learning (100% de incidentes reales sin retención).

### 1. Deterministic security pattern backstop (extender `quality-gate.js`)
- **Expected Autonomy Gain:** VERY_HIGH — cierra la brecha más severa medida (75% miss rate, en el modo de trabajo por defecto).
- **Implementation Cost:** MEDIUM — reutiliza el hook existente (WARN-only, fail-open ya establecido), requiere diseño cuidadoso de patrones para minimizar falsos positivos.
- **Regression Risk:** LOW-MEDIUM — aditivo, no bloqueante, no toca runtime crítico.
- **Token Impact:** ninguno (hook, no contexto).
- **ROI:** VERY_HIGH.

### 2. Persistir lecciones de incidentes reales a Engram en el momento del fix
- **Expected Autonomy Gain:** VERY_HIGH — cierra un gap de 100% miss rate en la dimensión de menor score absoluto (12.5%).
- **Implementation Cost:** LOW — cambio de disciplina/proceso ("tras un root-cause fix real, `mem_save` con topic_key del incidente"), no arquitectura nueva, reutiliza infraestructura Engram ya probada (funciona para decisiones de alto nivel, confirmado esta sesión).
- **Regression Risk:** LOW — puramente aditivo, fail-open si Engram no está disponible.
- **Token Impact:** mínimo (una escritura por incidente confirmado, no por sesión).
- **ROI:** VERY_HIGH.

### 3. Evidence-content requirement en `qa_strict` (no solo estructura)
- **Expected Autonomy Gain:** HIGH — cierra el gap central del benchmark (existencia de validador ≠ evidencia real).
- **Implementation Cost:** MEDIUM-HIGH — toca `atlas_dispatcher.py` (runtime), requiere diseño de compatibilidad retroactiva con envelopes legacy.
- **Regression Risk:** MEDIUM — un cambio mal diseñado podría bloquear envelopes legítimos que hoy pasan sin `screenshot_path` en tareas no-visuales.
- **Token Impact:** ninguno.
- **ROI:** HIGH (menor que #1/#2 por mayor costo/riesgo de implementación — candidato a pasar por el Architecture Decision Governor antes de tocar código, dado que "touches_runtime" típicamente resulta en `NEEDS_EVIDENCE` o `NEEDS_HUMAN_APPROVAL`).

**Model Selection dinámico** queda registrado como candidato **MEDIUM** de
ROI (gap real pero parcial, sobre un diseño conocido) — no se recomienda
como prioridad inmediata sin más evidencia de fricción real en proyectos.

---

## 12. Validación del benchmark (no rompió ATLAS)

| Check | Resultado |
|-------|-----------|
| `atlas_healthcheck.py` | 24 PASS / 2 WARN / 0 FAIL |
| `run_all.py --quick` | 38/38 PASS |
| `run_all.py --release` | 41/41 PASS |
| `secrets_check.py` | limpio |
| `claim_linter.py --summary` | 0 HIGH / 0 CRITICAL |
| `git diff --check` | limpio |
| Proyectos externos | intactos (`lucas-rojo-web/*` sin tocar) |
| Reverificación en vivo (3 hechos class_a) | 3/3 idénticos a lo registrado |

---

## 13. Reproducibilidad

- `config/autonomy_benchmark_v1.yaml` — casos + rubricas + veredictos.
- `tools/autonomy_benchmark.py` — scorer. `--reverify` re-ejecuta en vivo los
  hechos class_a determinísticos (fixtures de seguridad reales, gate de
  evidencia QA). Los casos class_b/class_c están documentados con su prompt
  exacto o su commit/evidencia — reproducibles manualmente, no
  auto-ejecutados en cada corrida (evita costo/no-determinismo de
  re-generar subagentes en cada invocación).
- `autonomy-benchmark-v1.json` — output runtime, regenerable, no
  necesariamente versionado.

---

## 14. Advertencia de honestidad

Este benchmark reporta **69.9%**, no un número ajustado para verse mejor.
Ningún caso fue rediseñado tras ver el resultado. Ningún PARTIAL fue
promovido a PASS. El score más bajo (Learning, 12.5%) y el hallazgo más
crítico (Security, 6/8 categorías sin detección en el modo de trabajo por
defecto) se reportan exactamente como se midieron.

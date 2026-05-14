# Intent Clarifier — Paso 0 de ATLAS

> Protocolo obligatorio antes de spawnear cualquier subagente cuando el brief del usuario es ambiguo o incompleto.
> Vive antes del orquestador. Si el clarifier no se activa, el orquestador asume brief válido.

---

## 1. Cuándo activar el clarifier

Activar **si el brief carece de ≥ 2 de estos 4 elementos**:

1. **Objetivo concreto** — qué problema resuelve o qué entrega.
2. **Tipo de trabajo** — proyecto nuevo / modificación / diagnóstico / planificación.
3. **Restricciones** — stack, plazos, presupuesto, plataforma.
4. **Definición de éxito** — cómo se sabe que está terminado.

> Heurística: si releés el brief y no podés describir el resultado en 1 frase, activar.

---

## 2. Cuándo NO activar

- El usuario explicitó modo y proyecto: `"modo diagnóstico sobre REYESOFT — solo lectura"`.
- Brief cubre los 4 elementos.
- El trabajo cabe en **Modo Rápido** (ver sección 2 de `ATLAS.md`).
- El usuario pidió explícitamente saltarse el clarifier: `"sin clarifier, asumí defaults"`.

---

## 3. Qué hacer cuando se activa

ATLAS pausa **antes** de cualquier `mem_session_start` o spawn de subagente y formula estas 4 preguntas en bloque (no de a una):

1. ¿Cuál es el objetivo medible de este trabajo?
2. ¿Es un proyecto nuevo, una modificación, un diagnóstico o solo planificación?
3. ¿Hay restricciones (stack, plazo, presupuesto, plataforma)?
4. ¿Qué cuenta como "terminado"? Cita un criterio de aceptación.

Adicional opcional (si aplica):
- ¿Quién es el usuario final / consumidor del entregable?
- ¿Hay datos sensibles, integraciones existentes o dependencias críticas?

---

## 4. Output del clarifier

Una vez recibidas las respuestas, ATLAS consolida un **brief canónico de 6-8 líneas** con esta forma:

```
PROYECTO: <nombre o tópico>
MODO: diagnóstico | planificación | ejecución | modificación
OBJETIVO: <1 frase>
USUARIOS: <quién consume el entregable>
RESTRICCIONES: <stack/plazos/etc, o "ninguna">
ÉXITO: <criterio de aceptación verificable>
RIESGOS_CONOCIDOS: <opcional, solo si el usuario los nombró>
```

Este brief es el **input canónico de Fase 1**. El orquestador no recibe el brief crudo del usuario — recibe esta versión consolidada.

---

## 5. Reglas duras

- El clarifier NO inventa respuestas. Si el usuario evade, el clarifier reformula. Después de 2 intentos sin respuesta clara, ATLAS aborta y vuelve a Modo Rápido.
- El clarifier NO consume tokens en subagentes. Es una conversación directa con el usuario.
- El clarifier NO escribe en Engram. La sesión Engram empieza recién en el paso "Open" del ciclo, con el brief canónico.
- El clarifier es invisible si el brief ya es válido. No agrega fricción innecesaria.

---

## 6. Ejemplo

**Brief vago del usuario:**
> "Hacé algo con la app de REYESOFT."

**Clarifier activa** (faltan 3 de 4 elementos: objetivo, tipo, éxito).

**Respuesta del usuario tras preguntas:**
> "Modo diagnóstico, sobre el flujo de login. Quiero saber si hay riesgos de seguridad. Stack actual Next.js 15. Éxito: lista de hallazgos OWASP priorizados."

**Brief canónico generado:**
```
PROYECTO: REYESOFT (flujo de login)
MODO: diagnóstico
OBJETIVO: detectar riesgos de seguridad en el flujo de login
USUARIOS: equipo de desarrollo REYESOFT
RESTRICCIONES: stack Next.js 15, sin tocar código
ÉXITO: lista de hallazgos OWASP priorizados
RIESGOS_CONOCIDOS: -
```

→ Orquestador recibe esto y arranca Fase 1 con foco en `security-engineer`.

# Protocolo obligatorio de QA visual y UX/UI

> **Fuente única de verdad.** Esta política aplica a **toda tarea que cambie una
> interfaz visual** (web, landing, app, componente, animación, asset) en
> **cualquier proyecto** operado con ATLAS, en modo orquestador y en modo Claude
> normal. Los agentes (`evidence-collector`, `reality-checker`, `frontend-developer`,
> `git`, `deployer`, `orquestador`) la referencian; no copian sus reglas.
>
> Versión 1.0 · 2026-10-27 · aprobada por Lucas.

## Principio

Compilar no significa terminado. Una tarea visual termina cuando la experiencia
**renderizada en un navegador real** cumple el diseño aprobado y funciona en
desktop, tablet y móvil, y hay evidencia verificable de eso. Lint, build y tests
unitarios son necesarios, pero no alcanzan.

## Reglas

1. **Navegador real.** Abrir la aplicación con Playwright (o la herramienta de
   navegador disponible), inspeccionar el resultado renderizado y comprobar que
   funciona. Preferir el build de producción (`build` + `start`) al dev server.
2. **Comparación con el diseño aprobado.** Verificar composición, proporciones,
   jerarquía visual, tipografías, colores, nitidez, animaciones e interacciones
   contra la referencia aprobada. Funcionar técnicamente no es estar terminado.
3. **Responsive real.** Probar desktop **1440 px**, tablet **768 px** y móvil
   **390 px**: navegación táctil, legibilidad, rendimiento, sin desbordes. No
   alcanza con reducir la escala: cada dispositivo necesita una composición usable.
4. **Pruebas funcionales.** Hover, clic/tap, navegación, estados, animaciones,
   errores de consola y comportamiento con `prefers-reduced-motion`. Cada
   elemento interactivo tiene que ejecutar su función de verdad.
5. **Evidencia visual.** Capturas de las tres resoluciones y video cuando haya
   animación. Compararlas con el diseño aprobado, identificar diferencias y
   corregirlas **antes** de pedir validación al usuario.
6. **Criterios de aceptación.** No cerrar una tarea visual ni proponer
   merge/deploy con defectos importantes de UX/UI: imágenes borrosas, elementos
   desproporcionados, interacciones rotas, problemas responsive.
7. **Autonomía.** Ejecutar el ciclo **inspección → detección → corrección →
   nueva inspección** sin depender de que el usuario descubra los errores. Repetirlo
   después de **cada cambio relevante**, no solo al final.
8. **Sin navegador no hay aprobación.** Si no se puede abrir un navegador, el QA
   visual queda **PENDIENTE** y la tarea **BLOCKED**. Nunca declararlo aprobado ni
   degradarlo a "code-only" en una tarea con UI visible.
9. **Assets insuficientes se informan, no se disimulan.** Si una imagen no tiene
   resolución suficiente, faltan assets o una técnica no permite lograr el
   resultado, decirlo explícitamente: qué asset, tamaño actual, tamaño mínimo
   necesario y en qué estado/viewport falla. Detener la implementación visual que
   depende de ese recurso. No improvisar una solución visual inferior.
10. **Nada incompleto como final.** No presentar una versión con defectos
    bloqueantes como resultado terminado. Si hay bloqueantes, el estado es
    `BLOCKED`, no `DONE`.

## Estados de una tarea visual

| Veredicto de `visual_qa.py` | Estado de la tarea | Qué se puede hacer |
|---|---|---|
| `PASS` | `READY_FOR_APPROVAL` | Pedir aprobación al usuario con la evidencia. `DONE` solo después de su aprobación. |
| `PENDING_REVIEW` | `BLOCKED` | Falta la revisión de fidelidad contra la referencia (`review`). |
| `FAIL` | `BLOCKED` | Corregir y volver a inspeccionar. Si el defecto es de asset, informar (regla 9). |
| `PENDING` | `BLOCKED` | No hubo navegador. Informar "QA visual pendiente". |

## Cómo se ejecuta

```bash
# 1. Levantar la app (Windows/Claude Desktop: preview_start; ver docs/atlas-build-reference.md)
# 2. Inspeccionar en navegador real, con la referencia aprobada
python tools/visual_qa.py run --url http://localhost:3000/ruta --project <dir> \
    --reference <diseno-aprobado.png>
# 3. Mirar comparacion.jpg + capturas + videos y registrar la revisión de fidelidad
python tools/visual_qa.py review --report <dir>/qa/visual/<run>/report.json --review review.json
# 4. Antes de merge/deploy
python tools/visual_qa.py gate --project <dir>
```

`run` genera en `<proyecto>/qa/visual/<timestamp>/`: `desktop|tablet|mobile.png`,
`*-full.png`, `*.webm`, capturas de cada estado tras interactuar (`*-state-N.png`),
`desktop-reduced-motion.png`, `comparacion.jpg`, `raw.json`, `report.json` y
`report.md`. `qa/visual/latest.json` apunta al último reporte (agregar `qa/visual/`
al `.gitignore` del proyecto).

`review.json` (lo escribe quien miró las capturas: agente multimodal o persona):

```json
{
  "reviewer": "evidence-collector",
  "screenshots_reviewed": ["comparacion.jpg", "desktop.png", "tablet.png", "mobile.png"],
  "dimensions": {"composition": 0, "proportions": 0, "typography": 0, "color": 0,
                 "sharpness": 0, "motion": 0, "interaction": 0},
  "differences": ["diferencia concreta vs la referencia", "..."]
}
```

## Umbrales

| Chequeo | Severidad | Regla |
|---|---|---|
| Imagen mostrada a más de 1.05 px CSS por px fuente (en reposo **o tras una interacción**, ej. zoom) | CRITICAL | Borrosa. Regenerar el asset. |
| Imagen a más de 1.5 px de pantalla por px fuente (DPR 2) | MEDIUM | Blanda en retina. |
| Imagen deformada > 3% | HIGH | Desproporcionada. |
| Desborde horizontal | HIGH | |
| Controles táctiles < 44×44 px (tablet/móvil) | HIGH | |
| Excepción de página / 5xx | CRITICAL | |
| `console.error`, recurso 4xx, request fallido | HIGH | |
| Interacción sin efecto observable, tapada o inaccesible | HIGH | |
| Movimiento con `prefers-reduced-motion: reduce` | HIGH | |
| Animación sin video de evidencia | HIGH | |
| Viewport obligatorio sin probar | HIGH | |
| Fidelidad: promedio < 7/10 o alguna dimensión < 5 | HIGH | |
| CLS > 0.25 | HIGH · > 0.1 MEDIUM | |
| Texto < 12 px | MEDIUM (táctil) · LOW | |
| LCP > 4 s, imágenes sin `alt` | MEDIUM | |
| Sin feedback de hover, sin `<h1>` | LOW | |

CRITICAL y HIGH bloquean (`FAIL`). MEDIUM y LOW se informan.

## Enforcement

- `tools/visual_qa.py` es **fail-closed**: ante cualquier imposibilidad de
  verificar devuelve `PENDING` o `FAIL`, nunca `PASS`.
- `gate` exige un reporte `PASS` **del commit actual** (`git_head` == `HEAD`).
- Hook `visual-qa-gate.js` (PreToolUse/Bash, global): en proyectos con interfaz
  visual **bloquea** `gh pr merge`, `vercel deploy/--prod`, `netlify deploy` y
  `git push` a `main`/`master` sin gate OK. Bypass solo con autorización explícita
  del usuario: `ATLAS_VISUAL_QA_BYPASS=1` (documentar el motivo).
- Tests: `_qa/bloque-VQA-visual-qa-protocol.py`.

## Límites conocidos (honestidad)

- La detección de "interacción sin efecto" mide DOM/URL/scroll/foco/estado ARIA;
  un cambio puramente en `<canvas>` puede no verse. Revisarlo en el video.
- La fidelidad al diseño la juzga la revisión (`review`), no un algoritmo.
- Chromium headless no reproduce `<video>` HTML5 (ver `evidence-collector.md`).

# F15 Context7 + Playwright — CI Determinism Fix

**Fecha:** 2026-09-04
**Alcance:** exclusivamente `bloque-F15-context7.py` y `bloque-F15-playwright.py`.
No se tocó Deterministic Next Transition, `atlas_verify.py`, ni ningún otro archivo.

---

## Root cause exacto

**T4 en ambos archivos ejecutaba `npx -y <pkg> --version` con timeout 30s.** Esto
NO es una prueba de capability (¿está ATLAS configurado correctamente?) — es una
prueba accidental de acceso a npm (¿puede este proceso resolver y descargar un
paquete desde el registry de npm ahora mismo?). **`WRONG_CAPABILITY_TEST`**, la
clasificación primaria.

Causas compuestas, todas confirmadas con evidencia:

| Causa | Evidencia |
|-------|-----------|
| **COLD_NPX_FETCH** | `.github/workflows/ci.yml` usa `actions/setup-node@v4` **sin** parámetro `cache:` — el cache de npm está genuinamente vacío en cada corrida, no es una corazonada, es 0% de hit-rate estructural |
| **PACKAGE_NOT_DECLARED** | Ningún `package.json`/`package-lock.json` en la raíz del repo declara `@playwright/mcp` ni `@upstash/context7-mcp` — solo aparecen dentro de `.mcp.json` (config runtime, gitignored), como invocaciones `npx -y <pkg>` sin versión pinneada |
| **NETWORK_DEPENDENCY** | `npx -y <pkg>` SIEMPRE hace un round-trip al registry para resolver la versión — `-y` solo omite el prompt de confirmación de instalación, **no** significa "preferir cache local" |

**Por qué pasaba local y fallaba en CI:** localmente, `npx -y @playwright/mcp
--version` resuelve en ~1.5s porque el cache de npm de esta máquina ya tiene el
paquete (de invocaciones repetidas en sesiones previas). En un runner de GitHub
Actions fresco, el mismo comando debe: resolver DNS → consultar metadata del
paquete en registry.npmjs.org → descargar el tarball → extraerlo → recién
entonces ejecutar `--version`. Ese round-trip completo, en un runner compartido,
excedió 30s en **3 corridas consecutivas** — no es flakiness aleatoria, es un
timeout estructuralmente insuficiente para la operación que el test
accidentalmente le pide hacer.

**Confirmado con `npx --offline`:** localmente, `npx --offline -y @playwright/mcp
--version` responde en 1.2s (cache tibio) o falla en <1s con `ENOTCACHED`
(cache vacío, simulado con `NPM_CONFIG_CACHE` apuntando a un directorio vacío) —
prueba directa de que el problema es la dependencia de red, no el paquete en sí
ni Node/npm.

---

## Separación de conceptos (aplicada)

| Concepto | Qué prueba | Requiere red | Bloqueante en quick/release |
|----------|-----------|:---:|:---:|
| `REGISTERED` | Declarado en `config/mcp.registry.yaml` | No | Sí |
| `CONFIGURED` | `.mcp.json` runtime lo referencia | No | Sí (SKIP si `.mcp.json` ausente — comportamiento preexistente, sin cambios) |
| `PACKAGE_AVAILABLE` | El paquete existe en el cache **local** de npm | **No** (`--offline`) | Sí, pero PASS/SKIP — nunca FAIL por ausencia |
| `LIVE_REACHABLE` | El MCP responde **ahora**, con red real | Sí | **No** — opt-in, puramente informativo |

`Playwright registry LIVE` ya **no** implica "npx puede descargar el paquete
ahora" — son aserciones separadas, exactamente como pide la doctrina del pedido.

---

## Opciones evaluadas (FASE 6)

| Opción | Determinismo | Velocidad | Dependencia de red | Costo | False+ | False- | Mantenimiento |
|--------|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| 1. Package declarado + instalado por CI | Alto | Media (mueve el costo a un step de setup) | **Sigue dependiendo** (el `npm install` del setup necesita red) | Medio-alto (lockfile nuevo a mantener sincronizado con `mcp.registry.yaml` — mismo tipo de drift que ya causó un bug esta semana) | Bajo | Medio | Alto |
| 2. Prewarm/cache npm en CI | Medio | Mejora runs *posteriores*, no el primero/cache-miss | Sigue existiendo en cache-miss | Bajo | Medio (cache-miss sigue fallando) | — | Bajo, pero no resuelve el problema estructural |
| **3+4. `npx --offline` + SKIP en ausencia (elegida)** | **Alto** | **Alta** (falla rápido si ausente, sin esperar timeout) | **Ninguna** | **Bajo** | **Muy bajo** | Ninguno relevante (roturas reales — registry/mapping — se siguen detectando, ver P4/P5) | **Bajo** |
| 5. Aumentar timeout | Bajo (sigue sin ser determinístico) | Baja (empeora — más tiempo de espera) | Sigue existiendo | Mínimo | Sigue existiendo (solo pospuesto) | — | Bajo, pero no resuelve nada |

**Elegida: Opción 3+4 combinadas.** Es mejor que simplemente subir el timeout
porque:
1. Resuelve la causa estructural (dependencia de red innecesaria en el
   camino bloqueante de CI), no solo pospone el síntoma.
2. Es más rápida, no más lenta — falla en <1s en vez de esperar 30s/60s/lo-que-sea.
3. Preserva la detección real de roturas (P4/P5 abajo demuestran que un
   registry roto o un capability-mapping roto siguen dando FAIL genuino).
4. No introduce un lockfile nuevo que pueda desincronizarse de
   `config/mcp.registry.yaml` (el mismo patrón de drift que causó el bug de
   `atlas_verify.py` reparado esta misma semana).

---

## Diseño implementado

**T4 dividido en dos funciones**, en ambos archivos:

- `test_package_available_offline()` — reemplaza el T4 anterior. Usa
  `npx --offline -y <pkg> --version`, timeout 10s (generoso para una
  operación 100% local). PASS si resuelve, **SKIP** (no FAIL) si el paquete
  no está cacheado — un runner limpio sin el paquete preinstalado es un
  estado esperado, no una rotura.
- `test_live_reachable_diagnostic()` — nueva, opt-in (`ATLAS_RUN_NETWORK_DIAGNOSTIC=1`
  o flag `--network-diagnostic`), nunca llama `ok()`/`fail()` — imprime
  `[INFO]` únicamente, no puede afectar `PASS_COUNT`/`FAIL_COUNT`/exit code
  por construcción. No se ejecuta por defecto en quick/release/CI.

El resto de los tests (registry, capability mapping, `.mcp.json`,
capabilities coverage, `required_for`, capability layer, `validate_registry`)
**no se tocaron** — siguen siendo bloqueantes y deterministas como antes.

---

## §11 — Nota explícita: esto NO valida Browser E2E

Este fix resuelve el **contrato/configuración** del provider (F15). **No**
demuestra que Playwright/Chromium realmente lanza, navega, o toma
screenshots — eso ya fue validado por separado en
`docs/BROWSER-VISUAL-QA-DIAGNOSTIC.md` (diagnóstico anterior, con evidencia
real de Chromium: launch, navigation, DOM, click, screenshots multi-viewport,
console, network, integración con evidence-collector). Ambos diagnósticos
son complementarios y deliberadamente independientes.

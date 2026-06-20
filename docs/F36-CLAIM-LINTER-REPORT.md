# F36 — Claim Linter Report

**Fecha:** 2026-06-19
**Base:** ATLAS v1.0.0-rc2 (post-F35 `e4f37d0`)
**Modo:** gate de honestidad documental, **read-only, WARN-only**. Sin runtime/dispatcher/MCPs/deps; sin bloquear release; reversible.

---

## Qué se construyó

- **`tools/claim_linter.py`** — escanea Markdown por claims riesgosos (absolutos,
  técnicos, estado, seguridad, performance), los clasifica LOW/MEDIUM/HIGH/CRITICAL y
  mapea cada HIGH/CRITICAL a un verificador sugerido. CLI: `--scan`, `--summary`,
  `--json`, `--file`, `--all`. Read-only, offline.
- **`config/claim-linter.registry.yaml`** — patrones por categoría + severidad +
  verifier + whitelist de contexto descriptivo.
- **Healthcheck check `Claim linter`** — WARN-only (WARN si hay CRITICAL sin evidence
  mapping; nunca FAIL).

---

## Claims detectados (docs reales)

Scan del set por defecto (README, CONTRIBUTING, GLOSSARY, CLAUDE.md, atlas-*.md;
reportes históricos excluidos salvo `--all`):

| Severidad | Conteo |
|-----------|-------:|
| CRITICAL | 0 |
| HIGH | 0 (tras whitelist) |
| MEDIUM | 42 |
| LOW | 8 |
| **CRITICAL sin evidencia** | **0** |

**El claim peligroso real ("no raw MCP") ya había sido corregido en F27** — el linter
confirma que no quedan claims técnicos falsos en los docs actuales.

---

## Falsos positivos (6 HIGH iniciales → reclasificados)

El linter v1 marcó 6 HIGH que **no son claims falsos**, sino texto descriptivo o
invariantes ya verificadas. Se bajaron a LOW vía whitelist de contexto (no se debilitó
la detección de invariantes reales):

| Línea | Texto | Por qué no es claim falso |
|-------|-------|---------------------------|
| README:353-354 | "All agents, roles, tools" / "All hooks…" | descripción de tabla doc-map |
| CONTRIBUTING:30 | "Every hook exits 0 on empty input" | invariante **verificada** por healthcheck (hooks smoke test) |
| engram-ref:21 | "referencia para todos los agentes" | scoping descriptivo |
| build-ref:84 | "ningún agente creativo funciona sin brand.json" | regla real del pipeline (true by design) |
| build-ref:101 | "patterns que NO están en ningún agente" | scoping descriptivo |

Whitelist agregada: `roles, tools` · `writing guide` · `referencia para` · `funciona sin`
· `no están en ningún` · `exits 0 on empty`.

---

## Claims corregidos

**Ninguno.** No se encontraron claims claramente falsos en los docs actuales (el único
histórico falso, "no raw MCP", se corrigió en F27). Coherente con la regla "no arreglar
compulsivamente".

## Claims aceptados (MEDIUM advisory)

Los 42 MEDIUM son palabras absolutas ("never/nunca/siempre/always/fully") en
**reglas e invariantes intencionales y verdaderas**, p. ej.:
- "ATLAS is fail-open: … never breaks your base Claude" (cierto por diseño).
- "Never hardcode tokens" (instrucción, no claim de estado).
- "el orquestador NUNCA hace trabajo real" (regla de oro).
- "Lectura SIEMPRE en 2 pasos" / "Escritura SIEMPRE con topic_key" (doctrina Engram).
- "always-on" (factual: describe el costo de boot).

Son doctrina/reglas correctas, no promesas falsificables → **aceptados** (el linter
detecta riesgo, no juzga estilo).

---

## Verificadores mapeados (HIGH/CRITICAL)

| Claim | Verifier |
|-------|----------|
| no raw MCP / fully migrated | `grep mcp__` / `architecture_audit` |
| no secrets / cannot leak | `tools/secrets_check.py` |
| all tests pass | `tools/run_all.py --release` |
| release-ready / production-ready | `tools/run_all.py --release` |
| low-token / optimized / slim | `tools/boot_profiler.py --scan` |
| healthcheck/security claims | `tools/atlas_healthcheck.py` |

Detección sintética verificada: "no raw MCP"→HIGH, "no secrets"/"fully secure"→CRITICAL,
"all tests pass"→HIGH, "release-ready"→MEDIUM — todos con verifier.

---

## Riesgos y mitigaciones

| Riesgo | Mitigación |
|--------|------------|
| Falsos positivos (texto descriptivo) | Whitelist de contexto; severidad informativa; WARN-only |
| Ruido de reportes históricos | Excluidos del scan por defecto (solo con `--all`) |
| El linter no prueba el claim, solo lo señala | Mapea verifier; la verificación real es manual/CLI por ahora |
| Sobre-tuning del whitelist oculta claims reales | Whitelist solo baja a LOW (no elimina), CRITICAL nunca se baja |

---

## Próximos pasos

- **Mantener WARN-only.** Considerar `--strict` (FAIL en CRITICAL sin evidencia) solo
  si la honestidad documental se vuelve un gate de release deseado (decisión futura via
  Architecture Decision Governor).
- Auto-probe de más verifiers (hoy solo `no-raw-mcp` se auto-prueba); opcional.
- Integrar el linter en CI como job informativo (no bloqueante) — futuro.

---

## Validación

| Check | Resultado |
|-------|-----------|
| F36 claim-linter suite | 12/12 PASS |
| Linter scan (docs reales) | 0 CRITICAL, 0 HIGH, 0 sin-evidencia |
| Healthcheck "Claim linter" | PASS (WARN-only) |
| Quick / Release | (ver F36.7) |
| secrets / runtime | exit 0 / sin cambios de runtime |

# F25 — Integral Validation Report

**Fecha:** 2026-06-19
**Commit validado:** `51e5842` (+ fix local de display en `tools/projects_registry.py`)
**Tag de release:** `v1.0.0-rc2` → `51e5842`
**Release GitHub:** [v1.0.0-rc2](https://github.com/lkswally/Claude-Atlas/releases/tag/v1.0.0-rc2) (pre-release)
**Entorno local:** Windows 10 · Python 3.14.5 · Node v24.16.0 · npm v11.13.0

---

## 1. Estado Git

- Rama: `main`, up to date con `origin/main`
- Últimos commits relevantes: `51e5842` (fix release-ci), `398cfb5` (fix CI quick), `689a334` (F24 P5)
- Tags `v1.0.0*`: `v1.0.0-rc1` (histórico, Release Validation falló por bug de workflow), `v1.0.0-rc2` (válido, todo verde)
- Archivos no trackeados inofensivos en working tree: `run_all*.json`, `release-report.md` (artefactos de corridas), `lucas-rojo-web/*` (proyecto externo, fuera de scope)

---

## 2. Tests ejecutados y resultados

| Test | Comando | Resultado |
|------|---------|-----------|
| Quick suite | `run_all.py --quick` | **PASS=30 FAIL=0 / 30** · 40.5s · 2 skipped |
| Release suite | `run_all.py --release` | **PASS=33 FAIL=0 / 33** · ALL PASS |
| Release JSON | `run_all.py --release --json` | total **33** · passed **33** · failed **0** · skipped **0** · 59.25s |
| Healthcheck | `atlas_healthcheck.py` | **PASS=22 WARN=2 FAIL=0 / 24** · HEALTHY |
| Healthcheck strict | `atlas_healthcheck.py --strict` | **PASS=22 WARN=2 FAIL=0 / 24** · HEALTHY |
| Secrets check | `secrets_check.py` | 0/7 tokens configurados (todos opcionales/pending) · sin secretos filtrados |
| Test registry | `test_registry.py --summary` | 32 active · 32 legacy · quick=30 · release=32 · loaded OK |
| MCP registry | `mcp_registry.py --summary` | 21 MCPs · 12 LIVE · 2 PENDING_TOKEN · 1 DEFERRED_PAID |
| Projects registry | `projects_registry.py --summary` | 5 proyectos · 3 activos · paths OK (tras fix de encoding) |

---

## 3. Validación de componentes

| Componente | Estado | Detalle |
|------------|--------|---------|
| Hooks | ✅ PASS | 13/13 smoke OK (fail-open); block-no-verify y config-protection bloquean |
| Skills Registry | ✅ PASS | 10 skills · dominios: branding, design, orchestration, qa |
| Projects Registry | ✅ PASS | 5 registrados, 3 activos, paths OK |
| MCP Registry | ✅ PASS | 21 MCPs, 12 LIVE, engram runtime OK |
| Capability Router | ✅ PASS | resolve OK · browser=LIVE · documentation=LIVE · memory=LIVE |
| Capability Policy (F19) | ✅ PASS | 14 policies · ALLOW=7 WARN=7 BLOCK=0 |
| Test Registry | ✅ PASS | 32 active / 32 legacy, loaded sin error |
| Engram | ✅ PASS | ENGRAM_ACTIVE — binario OK, DB OK, search OK (local) |
| Context7 | ✅ PASS | registry CONFIG/LIVE · suite F15-context7 PASS |
| Playwright | ✅ PASS | suite F15-playwright PASS (Chromium SKIP en CI limpio) |
| Notion | ✅ PASS | status LIVE · suite F15-notion PASS |
| GitHub (pending token) | ⏳ PENDING_TOKEN | binario opcional; sin `GITHUB_TOKEN` → SKIP no-bloqueante |
| Vercel (pending token) | ⏳ PENDING_TOKEN | requiere `VERCEL_TOKEN`; no bloquea release |
| Runtime settings (expected/runtime) | ✅ PASS / ⚠️ WARN | "Expected config" PASS (fuente de verdad estable); `.claude/settings.json` runtime → WARN_RUNTIME_MUTABLE (esperado) |

---

## 4. Validación GitHub (CI/CD)

| Workflow | Rama/Tag | Conclusión |
|----------|----------|-----------|
| CI (Quick Suite) | `main` (51e5842) | ✅ success |
| Release Validation | `v1.0.0-rc2` | ✅ success |
| Release Validation | `v1.0.0-rc1` | ❌ failure (histórico — bug de workflow, ya corregido en rc2) |

---

## 5. Warnings (documentados, no bloqueantes)

1. **`.claude/settings.json` — WARN_RUNTIME_MUTABLE**: archivo gestionado por Claude Desktop en Windows. La config estable se valida en "Expected config" (PASS). Diseño intencional (F23/F24-P5).
2. **Capability metrics (F18) — 1782 líneas JSONL inválidas** en `capability-events.jsonl`: log append-only acumulado; el lector tolera líneas malformadas (no afecta exit code ni release). Candidato a limpieza/rotación futura.

---

## 6. Skips (dependencias opcionales en entorno limpio)

- **F13-engram-active** (CI): T1-T5, T8 SKIP cuando el binario Go de Engram está ausente.
- **F15-playwright**: Chromium cache SKIP si `ms-playwright` no instalado.
- **F15-github / F15-context7 / F15-playwright**: `.mcp.json` runtime SKIP si ausente en CI.
- **F14 T14**: probe CLI de Engram SKIP si binario ausente.
- **F9**: paths de proyectos hermanos SKIP si no existen (CI).
- Quick suite: 2 suites skipped por diseño (usar `--full` para incluirlas).

---

## 7. Dependencias opcionales

| Dependencia | Requerida para | Estado sin ella |
|-------------|----------------|-----------------|
| Engram (Go binary) | memoria persistente live | fail-open → disco fallback |
| Playwright + Chromium | QA visual | SKIP en suites |
| `GITHUB_TOKEN` | GitHub MCP | PENDING_TOKEN, no bloquea |
| `VERCEL_TOKEN` | deploy Vercel | PENDING_TOKEN, no bloquea |
| `MAGIC_21ST_KEY` | Magic MCP (UI paga) | DEFERRED_PAID, opcional |

---

## 8. Readiness final

**ATLAS v1.0.0-rc2 = LISTO como Release Candidate.**

- Quick local: 30/30 PASS
- Release local: 33/33 PASS
- Healthcheck (normal + strict): HEALTHY, 0 FAIL
- CI Quick + Release Validation en GitHub: success
- Sin secretos filtrados, sin FAIL en ningún gate
- WARNs y SKIPs todos documentados y esperados

---

## 9. Riesgos conocidos

1. **Es un RC, no GA.** Falta documentación completa, bootstrap installer y `doctor` command pulido antes del v1.0 final.
2. **MCPs token-gated** (GitHub, Vercel) no validados live hasta proveer tokens; quedan en PENDING_TOKEN.
3. **`capability-events.jsonl` crece sin rotación** — 1782 líneas inválidas acumuladas; conviene limpieza antes de GA.
4. **Dependencias externas opcionales en CI** se clasifican como SKIP; la cobertura live de esas rutas depende del entorno local (Windows/Claude Desktop).
5. **`v1.0.0-rc1` sigue publicado** como histórico con Release Validation en rojo (bug de workflow, no de producto) — puede confundir; rc2 es el RC válido.

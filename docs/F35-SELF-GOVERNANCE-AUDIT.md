# F35 — Self-Governance Audit (F13–F34)

**Fecha:** 2026-06-19
**Alcance:** revisar cómo ATLAS *decidió* a lo largo de F13–F34, no qué construyó.
**Modo:** análisis only.

---

## 1. Decisiones tomadas por evidencia propia

- **F24** clasificó FAIL vs SKIP vs WARN con criterio (RUNTIME_MUTABLE, SKIP de deps opcionales) — no aceptó "todo debe pasar".
- **CI/Release diagnosis**: identificó causas raíz (pydantic ausente, settings.json corrupto, divergencia ci.yml/release.yml) con logs, no por suposición.
- **F25**: detectó y arregló un bug propio (`projects_registry.py` cp1252) al documentar el comando.
- **F27**: verificó cada crítica contra evidencia; descartó las falsas, corrigió solo claims reales.
- **F28/F29**: midió antes de refactorizar; el boot profiler nació para no adivinar.
- **F31**: el Architecture Score evitó inflar resultados (62→62 honesto en F32).
- **F32/F33**: rechazó subir el score "haciendo desaparecer" contenido — extendió el scan a `refs/` para medir honestamente.

## 2. Decisiones ejecutadas por instrucción externa

- La **secuencia completa** F28→F34 (qué fase seguía) vino del usuario, no de ATLAS.
- La **estructura de cada fase** (qué refs crear, nombres, objetivos de tokens) fue dictada en el prompt.
- F26/F28 (auditar vibecoding, auditar boot) fueron disparadas externamente — ATLAS no propuso esas auditorías por sí mismo.
- Los **commits/push** se hicieron porque el prompt los pedía, dentro de reglas.

## 3. Dónde faltó fricción crítica

- ATLAS **no cuestionó** si cada fase valía la pena antes de ejecutarla — asumió que sí.
- No propuso **alternativas** a los planes dados (ej. ¿hacía falta F33 separado de F32?).
- No detectó proactivamente que el **boot cost** era el problema real hasta que una comparación externa (F26→F28) lo expuso.
- No mantenía un **registro de decisiones** (por qué sí / por qué no) — cada fase empezaba en frío.

## 4. Dónde aceptó claims sin verificar

- El **README** afirmaba "agents call resolve_capability, not a raw MCP tool" y CONTRIBUTING "no agent references raw MCP prefixes" — **falsos**, no detectados hasta F27 (crítica externa).
- "Capability router migrado" se asumió completo cuando era progresivo.
- Conteos ("25 healthcheck checks") quedaron desactualizados sin verificación.

## 5. Checks existentes que NO detectaron el problema

- **CI / Release / quick**: verdes con claims documentales falsos (no validan honestidad del README).
- **F10 drift**: no mira contenido semántico, solo hashes espejo.
- **Healthcheck**: no medía costo de contexto ni duplicación.
- **Capability suites (F16/F17)**: pasaban aunque hubiera prefijos MCP crudos en agentes.

## 6. Checks nuevos que SÍ lo detectaron

- **Boot Profiler (F29)**: cuantificó el costo always-on (CLAUDE.md 8.7K).
- **Architecture Audit (F31)**: detectó god-files, duplicación, oversized, entropía.
- **F27 claim audit**: cazó los claims absolutos falsos.
- **Knowledge Registry + healthcheck WARN (F29)**: vigila políticas de carga.

## 7. Problemas que siguen siendo invisibles

- **Honestidad documental automática**: nada valida que un claim del README sea cierto (sigue siendo manual).
- **Necesidad real de una fase**: no hay gate que pregunte "¿vale la pena este cambio?" → lo aborda el **Decision Governor (F35)**.
- **Sobreingeniería**: no había señal automática hasta F35.
- **Deriva de dependencias**: un import nuevo no dispara alarma (secrets_check mira tokens, no deps).
- **Decisiones sin trazabilidad**: no hay ADR automático de por qué se aceptó/rechazó algo.

---

## Conclusión

ATLAS razonaba bien **dentro** de cada fase (evidencia, honestidad, mediciones) pero
**obedecía la agenda** sin cuestionar el "qué sigue" ni el "vale la pena". El patrón a
corregir no es la calidad de ejecución — es la **ausencia de un gobernador de
decisiones** que aplique fricción crítica antes de actuar. Eso es exactamente lo que
introduce F35 (`architecture.decision-policy.yaml` + `architecture_decision.py`):
toda propuesta futura se clasifica por evidencia/riesgo (ACCEPT … NEEDS_HUMAN_APPROVAL)
antes de implementarse.

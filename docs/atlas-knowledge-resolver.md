# ATLAS — Knowledge Resolver (`resolve_knowledge`)

> Contrato del mecanismo oficial de carga contextual selectiva (F33/F34). Lazy ref:
> cargá este doc cuando necesites entender cómo elegir qué ref leer.

## Qué problema resuelve

ATLAS movió el conocimiento operativo de los god-files (CLAUDE.md, orquestador,
agent-protocol) a **muchas refs lazy** (F30/F32/F33). Con tantas refs, cargar "la
correcta" a mano es frágil. `resolve_knowledge(query)` mapea una **intención** a las
refs relevantes **sin leer su contenido** — devuelve metadata para que el caller
decida qué abrir. Es el reemplazo declarativo del "adivino qué ref necesito".

## `resolve_capability()` vs `resolve_knowledge()`

| | `resolve_capability()` (F16) | `resolve_knowledge()` (F33/F34) |
|---|---|---|
| Dominio | MCPs / herramientas (browser, memory…) | Conocimiento / refs markdown |
| Entrada | nombre de capability | intención / query libre |
| Salida | provider + status + fallback | refs (path + metadata) |
| Efecto | resolver qué tool usar | resolver qué documento leer |
| Fuente | `config/mcp.registry.yaml` | `config/knowledge.registry.yaml` |

Son complementarios: capability = "con qué ejecuto", knowledge = "qué necesito saber".

## Cuándo usarlo

- Antes de cargar un ref grande (pipeline, contracts): resolvé primero la pieza
  específica en vez de leer el índice entero o todo el ref.
- Ante una intención compleja (planning, execution, QA, release, memory): resolvé
  la query recomendada y cargá solo esa ref.

## Entradas aceptadas

Query libre, una o varias palabras. Se tokeniza y se scorea por término contra:
`id`, `category`, `trigger`, `tags`, nombre de archivo y `notes`. Entradas que
matchean **más términos** rankean más alto.

```bash
python tools/knowledge_resolver.py --list
python tools/knowledge_resolver.py --resolve "<query>"
python tools/knowledge_resolver.py --json "<query>"
```

## Salida (metadata-only)

Lista rankeada de `{id, path, category, load_policy, estimated_tokens, trigger, tags, reason, score}`.
**Nunca** incluye el contenido del archivo.

## Qué NO hace

- No lee ni inyecta el contenido de las refs (solo metadata).
- No toca el dispatcher ni el runtime; es un lookup sobre el registry.
- No decide por vos: rankea candidatos; vos cargás el que corresponda.
- No falla con query desconocida → devuelve `[]`.

## Ejemplos

| Query | Top ref |
|-------|---------|
| `resolve_knowledge("pipeline phase-1")` | `orchestrator-pipeline-phase-1.md` |
| `resolve_knowledge("frontend agent contract")` | `protocol-agent-contract-core.md` / índice de contratos |
| `resolve_knowledge("qa evidence")` | `protocol-agent-contract-evidence.md` |
| `resolve_knowledge("release gate")` | `atlas-release-reference.md` |
| `resolve_knowledge("engram")` | `protocol-memory-engram.md` |

## Mapa de intención → query recomendada

| Intención | Query |
|-----------|-------|
| planning | `pipeline phase-1` |
| architecture | `pipeline phase-2` |
| execution / dev | `pipeline phase-3` |
| certification | `pipeline phase-4` |
| publish / deploy | `pipeline phase-5` |
| QA / evidence | `qa evidence` |
| agent contract (por clase) | `<clase> agent contract` (ej. `frontend agent contract`) |
| release / CI | `release gate` |
| memory | `engram` |

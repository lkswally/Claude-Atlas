# Issue: Context7 MCP — flapping connection

**Fecha registro**: 2026-05-07
**Estado**: abierto, no resuelto, no en investigación activa
**Prioridad**: baja (no bloquea pipeline)

## Síntoma

`claude mcp list` reporta:
```
context7: npx -y @upstash/context7-mcp - ✗ Failed to connect
```

Conectó OK en la primera invocación tras `claude mcp add` y empezó a fallar en invocaciones posteriores.

## Evidencia recogida

- `~/.claude.json` (project: D:\ProyectosIA\ProyectosClaude) tiene la entrada `mcpServers.context7` con `command: npx -y @upstash/context7-mcp` — registro intacto.
- Sonda manual:
  ```
  npx -y @upstash/context7-mcp --help
  → 'context7-mcp' is not recognized as an internal or external command
  → exit 0
  ```
- Cambios de Fase 1 (settings.local.json + extraKnownMarketplaces) NO tocaron `~/.claude.json`. Verificado por hash + lectura.
- Cambios de Fase 2.1 (limpieza declarativa Engram) tampoco tocan MCP servers.

## Hipótesis

1. El paquete `@upstash/context7-mcp` no expone un bin resolvible por `npx --help`; el primer arranque vía protocolo MCP funcionó por ejecución indirecta.
2. Caché de `npx` corrupto o descarga incompleta tras el primer uso.
3. Cambio de versión del paquete que rompió el entry bin.

## Posibles vías de resolución (NO ejecutar todavía)

- Instalación global: `npm install -g @upstash/context7-mcp` y reapuntar el MCP server al binario global.
- Migrar a plugin oficial: existe `~/.claude/plugins/marketplaces/claude-plugins-official/external_plugins/context7/.mcp.json` — usar ese plugin en lugar del MCP server custom.
- Limpieza de caché: `npm cache clean --force` y reintentar.

## Restricciones

- No mezclar con la decisión de Engram.
- No abordar hasta nueva instrucción explícita.
- Si se resuelve, dejar registro del fix en este mismo archivo.

## Archivos relacionados

- `~/.claude.json` (entrada `mcpServers.context7` en projects/D:\ProyectosIA\ProyectosClaude)
- `~/.claude/plugins/marketplaces/claude-plugins-official/external_plugins/context7/.mcp.json` (plugin oficial alternativo no usado)

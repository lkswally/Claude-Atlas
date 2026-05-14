---
name: redis-patterns-reference
description: Referencia de patrones Redis (caching, pub/sub, HyperLogLog, cursor pagination). Cargado por backend-architect cuando el proyecto usa Redis.
---

# Redis Patterns Reference

### Caching strategy con Redis
- **Cache-aside**: leer cache → si miss, leer DB → guardar en cache con TTL
- **Invalidación**: invalidar cache en write operations (no TTL-only)
- **Keys**: `{entity}:{id}` (ej: `user:123`, `post:456`)
- **TTL por tipo**: sessions 24h, queries 5min, config 1h

### Redis patterns avanzados

#### Pub/Sub para real-time broadcasting
Cuando el proyecto tiene WebSocket/SSE, usar Redis Pub/Sub para broadcasting entre instancias:
```typescript
// Publisher (en el handler de API)
await redis.publish('chat:room-123', JSON.stringify({ user, message }));
// Subscriber (en el WebSocket server)
redis.subscribe('chat:room-123', (message) => {
  ws.clients.forEach(client => client.send(message));
});
```
Escala horizontalmente — cada instancia del servidor escucha el mismo canal.

#### HyperLogLog para conteo de visitantes únicos
Contar visitantes sin almacenar IDs individuales (< 1% error, memoria fija ~12KB):
```typescript
await redis.pfadd('visitors:2026-03-13', visitorId);
const count = await redis.pfcount('visitors:2026-03-13');
```

#### Keyspace notifications para invalidación de cache
Reaccionar automáticamente a expiración de claves:
```typescript
// Habilitar: CONFIG SET notify-keyspace-events Ex
redis.subscribe('__keyevent@0__:expired', (key) => {
  // Regenerar cache o notificar
});
```

### Pagination (cursor-based preferido)
```typescript
// Cursor-based (para feeds, listas infinitas)
{ cursor?: string, limit: number } → { items, nextCursor }
// Offset-based (para tablas con paginación numérica)
{ page: number, pageSize: number } → { items, total, totalPages }
```
Cursor-based es más performante en datasets grandes y evita skip/offset.

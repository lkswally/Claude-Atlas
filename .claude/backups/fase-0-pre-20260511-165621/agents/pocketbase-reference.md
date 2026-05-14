# PocketBase — Referencia (validado en producción)

Referencia técnica para proyectos que usan PocketBase como backend+DB.
Solo relevante cuando el proyecto específicamente usa PocketBase — no es el default del sistema.

## Gotchas validados

- **Boolean `required: true` rompe toggles**: Go trata `false` como zero value → falla validación. Campos booleanos que se van a alternar entre `true`/`false` NUNCA deben tener `required: true` en el schema.
- **listRule/viewRule deben diferenciar admin vs público**: si el admin panel necesita ver ítems ocultos, usar `published = true || @request.auth.collectionName = "admin_collection"`. Sin esto, el admin queda ciego a los registros ocultados.
- **Siempre exponer `errBody.data` en errores de API**: el `message` top-level es genérico ("Failed to update record."). El detalle real (qué campo falla, qué código de validación) está en `errBody.data`. Loguear ambos al debuggear.
- **Superadmin auth cambió en v0.23+**: el endpoint `/api/admins/auth-with-password` devuelve 404 en versiones nuevas. Usar `/api/collections/_superusers/auth-with-password` con el mismo body `{identity, password}`.
- **Reglas de coleccion son independientes por operacion**: create/list/update/delete pueden tener reglas distintas. Una coleccion puede permitir create a usuarios pero tener update en null (solo admin). Verificar las 4 reglas al debuggear 400/403.
- **NULL vs empty string en rules**: `NULL` listRule = solo admins (403). `""` = acceso publico. Son distintos en SQLite — verificar con `QUOTE(listRule)`.
- **Sort fields**: `sort=campo1,campo2` multi-campo retorna 400 en muchas versiones. `sort=-created` tambien puede fallar. Solucion segura: `sort=-id` (timestamp-based, time-sortable desde v0.16+).
- **PocketBase en Docker**: no tiene `sqlite3` dentro del container. Siempre `docker stop` antes de editar `.db` directamente.
- **HTTPS obligatorio**: si frontend es HTTPS, backend DEBE ser HTTPS. Ver `devops-vps-reference.md` para soluciones.

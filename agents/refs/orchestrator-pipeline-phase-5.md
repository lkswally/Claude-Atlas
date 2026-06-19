# Orchestrator Pipeline — FASE 5 (Publicación)

> Lazy phase ref extracted from orchestrator-pipeline.md in F33. Verbatim — behavior unchanged.
> Load via the pipeline index when this phase is active.

### FASE 5 — Publicación (solo con confirmación del usuario)

#### Si el usuario elige "s" o "g" — Git

Delega a **git**:
- Recibe: nombre del proyecto + rama (`main` siempre) + mensaje de commit sugerido
- Hace: verifica branch es `main` (renombra si es `master`) + `git add` + `git commit` + `git push` + setea default branch en GitHub
- Devuelve: STATUS + URL del repo + hash del commit + **info para deployer** (repo URL, branch, primer push sí/no)
- Guarda en Engram: `{proyecto}/git-commit`

Muestra al usuario:
```
✓ Commit subido
Repo: {url-github}
Commit: {hash} — "{mensaje}"
Branch: main (default)
```

#### Si el usuario eligió "s" — Deploy (solo después del git exitoso)

**Routing por tipo de proyecto:**
- **Web (DAG State `tipo` ≠ `mobile`)**: deployer en modo Vercel (default)
- **Mobile (DAG State `tipo: mobile`)**: deployer en modo EAS Build

**Modo Vercel** (web):
Delega directamente a **deployer** sin pedir confirmación adicional (el usuario ya eligió "s" o pre-autorizó el deploy):
- Recibe: directorio del proyecto + nombre + **info del git** (repo URL, branch, primer push) + `deploy_mode: "vercel"`
- Si es primer deploy: `vercel deploy --prod` + `vercel git connect` (activa auto-deploy)
- Si ya tiene Git Integration: verifica que el auto-deploy se disparó correctamente
- Devuelve: URL limpia del proyecto + estado de Git Integration + auto-deploy activo/no
- Guarda en Engram: `{proyecto}/deploy-url`

**Modo EAS Build** (mobile):
Delega a **deployer** con:
- Recibe: directorio del proyecto + nombre + `deploy_mode: "eas"` + `platform: "android" | "ios" | "both"` (preguntar al usuario si no especificó)
- Primer build: configura EAS + build preview
- Devuelve: URL de descarga del build en EAS + plataformas buildeadas
- Guarda en Engram: `{proyecto}/deploy-url`
- **Nota**: submit a stores requiere confirmación explícita adicional del usuario

**Handoff git→deployer**: el orquestador pasa la info que git devolvió directamente al deployer. Esto permite que deployer sepa si necesita conectar Git Integration o si ya está activa.

Muestra al usuario:
```
Deployado en {Vercel | EAS Build}
URL: {url-limpia | url-descarga-build}
```

**Si git retorna fallido:**
1. Presentar error al usuario (auth, conflict, remote, etc.)
2. Ofrecer: a) reintentar, b) cambiar remote/branch, c) exportar archivos sin git

**Si deployer retorna fallido:**
1. Presentar error al usuario (auth, build, config, etc.)
2. Ofrecer: a) reintentar, b) deploy manual (`vercel deploy --prod`), c) generar instrucciones de deploy paso a paso

Actualiza DAG State: fase_actual → "completado"

#### Resumen final del proyecto
Al completar Fase 5 (o si el usuario dice "terminamos"), presentar:
- Total de tareas completadas / total
- URL del repo (si git) + URL del deploy (si deployer)
- Si existe `{proyecto}/costs` en Engram: mostrar desglose de costos del pipeline creativo
- Llamar `mem_session_summary` + `mem_session_end`

---


# Better Auth 1.5 — Referencia para Agentes

## Resumen

Better Auth es la libreria de autenticacion estandar para todos los proyectos que necesiten login. Es framework-agnostic, basada en TypeScript, con soporte nativo para OAuth social, email/password, plugins (2FA, username, magic link, passkey, RBAC, organizaciones) y multiples database adapters.

**Instalacion**: `pnpm install better-auth` (o npm/bun)

---

## 1. Configuracion del Servidor (auth.ts)

```typescript
import { betterAuth } from "better-auth";

export const auth = betterAuth({
  baseURL: process.env.BETTER_AUTH_URL, // URL base del servidor

  // --- Database ---
  // Opcion A: URL directa (usa Kysely internamente)
  database: {
    provider: "pg", // "pg" | "mysql" | "sqlite"
    url: process.env.DATABASE_URL,
  },

  // --- Email/Password ---
  emailAndPassword: {
    enabled: true,
  },

  // --- Social Providers ---
  socialProviders: {
    google: {
      clientId: process.env.GOOGLE_CLIENT_ID!,
      clientSecret: process.env.GOOGLE_CLIENT_SECRET!,
    },
    github: {
      clientId: process.env.GITHUB_CLIENT_ID!,
      clientSecret: process.env.GITHUB_CLIENT_SECRET!,
    },
    discord: {
      clientId: process.env.DISCORD_CLIENT_ID!,
      clientSecret: process.env.DISCORD_CLIENT_SECRET!,
    },
    // Otros: apple, facebook, twitter, microsoft, spotify, twitch, linkedin
  },
});
```

---

## 2. Database Adapters

### Prisma Adapter
```typescript
import { betterAuth } from "better-auth";
import { prismaAdapter } from "better-auth/adapters/prisma";
import { PrismaClient } from "@prisma/client";

const prisma = new PrismaClient();

export const auth = betterAuth({
  database: prismaAdapter(prisma, {
    provider: "postgresql", // "postgresql" | "mysql" | "sqlite"
  }),
  emailAndPassword: { enabled: true },
});
```

### Drizzle Adapter
```typescript
import { betterAuth } from "better-auth";
import { drizzleAdapter } from "better-auth/adapters/drizzle";
import { db } from "./database";

export const auth = betterAuth({
  database: drizzleAdapter(db, {
    provider: "pg", // "pg" | "mysql" | "sqlite"
  }),
});
```

### Generar esquema de DB
```bash
# Genera tablas necesarias (user, session, account, verification)
npx @better-auth/cli generate
# O push directo a la DB:
npx @better-auth/cli migrate
```

---

## 3. Integraciones por Framework

### Next.js (App Router)
```typescript
// app/api/auth/[...all]/route.ts
import { auth } from "@/lib/auth";
import { toNextJsHandler } from "better-auth/next-js";

export const { GET, POST } = toNextJsHandler(auth);
```

**Middleware (Next.js 13–15)**:
```typescript
// middleware.ts
import { NextRequest, NextResponse } from "next/server";
import { getSessionCookie } from "better-auth/cookies";

export async function middleware(request: NextRequest) {
  const sessionCookie = getSessionCookie(request);
  const { pathname } = request.nextUrl;

  if (sessionCookie && ["/login", "/signup"].includes(pathname)) {
    return NextResponse.redirect(new URL("/dashboard", request.url));
  }
  if (!sessionCookie && pathname.startsWith("/dashboard")) {
    return NextResponse.redirect(new URL("/login", request.url));
  }
  return NextResponse.next();
}

export const config = {
  matcher: ["/dashboard/:path*", "/login", "/signup"],
};
```

> ⚠️ **Next.js 16+**: `middleware.ts` está deprecado para Better Auth. Usar `proxy.ts` con `export async function proxy()` en su lugar. Consultar la documentación de Better Auth para la implementación actualizada.

### Nuxt
```typescript
// server/api/auth/[...all].ts
import { auth } from "~/lib/auth";
import { toNodeHandler } from "better-auth/node";

const handler = toNodeHandler(auth);
export default defineEventHandler((event) => handler(event.node.req, event.node.res));
```

**Middleware Nuxt**:
```typescript
// middleware/auth.global.ts
import { authClient } from "~/lib/auth-client";

export default defineNuxtRouteMiddleware(async (to) => {
  const { data: session } = await authClient.useSession(useFetch);
  if (!session.value && to.path.startsWith("/dashboard")) {
    return navigateTo("/login");
  }
});
```

### Astro
```typescript
// src/pages/api/auth/[...all].ts
import { auth } from "@/lib/auth";
import type { APIRoute } from "astro";

export const ALL: APIRoute = async (ctx) => {
  return auth.handler(ctx.request);
};
```

**Middleware Astro**:
```typescript
// src/middleware.ts
import { auth } from "@/auth";
import { defineMiddleware } from "astro:middleware";

export const onRequest = defineMiddleware(async (context, next) => {
  const isAuthed = await auth.api.getSession({
    headers: context.request.headers,
  });
  context.locals.user = isAuthed?.user ?? null;
  context.locals.session = isAuthed?.session ?? null;
  return next();
});
```

### Express / Hono / Fastify
```typescript
// Express
import { toNodeHandler } from "better-auth/node";
import { auth } from "./auth";
app.all("/api/auth/*", toNodeHandler(auth));

// Hono
import { toHonoHandler } from "better-auth/hono";
app.all("/api/auth/*", toHonoHandler(auth));
```

---

## 4. Cliente (auth-client.ts)

```typescript
// Cliente generico (vanilla JS)
import { createAuthClient } from "better-auth/client";
export const authClient = createAuthClient({
  baseURL: "http://localhost:3000", // opcional si mismo dominio
});

// React
import { createAuthClient } from "better-auth/react";
export const authClient = createAuthClient({
  baseURL: "http://localhost:3000",
});

// Vue
import { createAuthClient } from "better-auth/vue";
export const authClient = createAuthClient({
  baseURL: "http://localhost:3000",
});

// Svelte
import { createAuthClient } from "better-auth/svelte";

// Solid
import { createAuthClient } from "better-auth/solid";
```

---

## 5. Uso del Cliente

### Sign Up
```typescript
await authClient.signUp.email({
  email: "user@example.com",
  password: "password123",
  name: "User Name",
});
```

### Sign In (email)
```typescript
await authClient.signIn.email({
  email: "user@example.com",
  password: "password123",
}, {
  onSuccess: (ctx) => { /* redirect */ },
  onError: (ctx) => { alert(ctx.error); },
});
```

### Sign In (social)
```typescript
await authClient.signIn.social({
  provider: "google", // "github" | "discord" | "apple" | etc
  callbackURL: "/dashboard",
});
```

### Session (React hook)
```typescript
const { data: session, isPending } = authClient.useSession();
// session.user, session.session
```

### Sign Out
```typescript
await authClient.signOut();
```

### Get Session (server-side)
```typescript
const session = await auth.api.getSession({
  headers: request.headers,
});
```

---

## 6. Plugins Comunes

```typescript
import { betterAuth } from "better-auth";
import { username } from "better-auth/plugins/username";
import { twoFactor } from "better-auth/plugins/two-factor";
import { organization } from "better-auth/plugins/organization";
import { magicLink } from "better-auth/plugins/magic-link";

export const auth = betterAuth({
  plugins: [
    username(),
    twoFactor(),
    organization(),
    magicLink({
      sendMagicLink: async ({ email, token, url }) => {
        // enviar email con el magic link
      },
    }),
  ],
});
```

Cliente con plugins:
```typescript
import { createAuthClient } from "better-auth/react";
import { usernameClient } from "better-auth/client/plugins";
import { twoFactorClient } from "better-auth/client/plugins";

export const authClient = createAuthClient({
  plugins: [usernameClient(), twoFactorClient()],
});
```

---

## 7. Variables de Entorno Requeridas

```env
BETTER_AUTH_URL=http://localhost:3000
BETTER_AUTH_SECRET=random-secret-min-32-chars

# Database
DATABASE_URL=postgresql://user:pass@host:5432/db

# Social providers (solo los que se usen)
GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=
GITHUB_CLIENT_ID=
GITHUB_CLIENT_SECRET=
DISCORD_CLIENT_ID=
DISCORD_CLIENT_SECRET=
```

---

## 8. Tablas de DB Requeridas

Better Auth necesita estas tablas minimas (generadas con CLI):
- **user**: id, name, email, emailVerified, image, createdAt, updatedAt
- **session**: id, userId, token, expiresAt, ipAddress, userAgent, createdAt, updatedAt
- **account**: id, userId, accountId, providerId, accessToken, refreshToken, expiresAt, ...
- **verification**: id, identifier, value, expiresAt, createdAt, updatedAt

---

## 9. Bundle Minimo (optimizacion)

Para reducir el bundle eliminando Kysely (cuando se usa Prisma/Drizzle):
```typescript
import { betterAuth } from "better-auth/minimal";
import { prismaAdapter } from "better-auth/adapters/prisma";

export const auth = betterAuth({
  database: prismaAdapter(prisma, { provider: "postgresql" }),
});
```

---

## 10. Decision de Stack Rapida

| Proyecto | DB Adapter | Framework Integration |
|----------|-----------|----------------------|
| Next.js + Prisma | prismaAdapter | toNextJsHandler + middleware |
| Next.js + Drizzle | drizzleAdapter | toNextJsHandler + middleware |
| Nuxt + Prisma | prismaAdapter | toNodeHandler + Nuxt middleware |
| Astro + cualquiera | prismaAdapter/drizzleAdapter | handler + Astro middleware |
| Express API | URL directa o adapter | toNodeHandler |
| Hono API | URL directa o adapter | toHonoHandler |

Siempre preferir Better Auth sobre Clerk, Supabase Auth o JWT custom para proyectos nuevos.

---

## Better Auth + Supabase + Vercel + Next.js 16 (validado en producción)

### Driver de DB: postgres.js, NUNCA pg
- Usar `postgres` (postgres.js) — paquete npm `postgres`. Es pure JS, sin bindings nativos.
- **NUNCA usar `pg`** (node-postgres) en Vercel serverless — usa bindings nativos de C++ que no existen en el runtime de Vercel.
- Instalar: `npm install postgres drizzle-orm better-auth`

### Conexión a Supabase desde Vercel: Transaction Pooler obligatorio
- **Vercel es IPv4-only**. La conexión directa de Supabase (`db.xxx.supabase.co:5432`) es IPv6. No funciona.
- **SIEMPRE usar el Transaction Pooler** (puerto 6543): `postgresql://postgres.PROJECT_REF:PASSWORD@aws-X-REGION.pooler.supabase.com:6543/postgres`
- **Verificar el host SIEMPRE en Supabase dashboard** → botón Connect → pestaña ORMs. El número de host varía por proyecto (`aws-0`, `aws-1`, `aws-2`...). NO asumir.
- **`prepare: false` obligatorio**: pgbouncer (Transaction Pooler) no soporta prepared statements. Sin esto, Better Auth falla silenciosamente con 500 y body vacío.

### Route handler: dynamic imports + clean request
Next.js 16 usa Turbopack que bundlea incorrectamente los módulos de DB con imports estáticos. Patrón obligatorio:

```typescript
// app/api/auth/[...all]/route.ts
export const dynamic = "force-dynamic";

let _auth: any = null;

async function getAuth() {
  if (_auth) return _auth;
  const { betterAuth } = await import("better-auth");
  const { drizzleAdapter } = await import("better-auth/adapters/drizzle");
  const { drizzle } = await import("drizzle-orm/postgres-js");
  const postgres = (await import("postgres")).default;
  const schema = await import("@/lib/schema");

  const client = postgres(process.env.DATABASE_URL!, {
    ssl: "require", max: 1, idle_timeout: 20, connect_timeout: 10, prepare: false,
  });
  const db = drizzle(client, { schema });

  _auth = betterAuth({
    baseURL: process.env.BETTER_AUTH_URL,
    secret: process.env.BETTER_AUTH_SECRET,
    database: drizzleAdapter(db, { provider: "pg" }),
    emailAndPassword: { enabled: true },
    // ... resto de config
  });
  return _auth;
}

// Next.js 16 pasa Request objects con propiedades internas que Better Auth
// no maneja. Reconstruir un Request limpio con solo los headers necesarios.
function toCleanRequest(req: Request, body?: string | null): Request {
  const url = new URL(req.url);
  const cleanUrl = (process.env.BETTER_AUTH_URL || "") + url.pathname + url.search;
  const headers = new Headers();
  headers.set("content-type", req.headers.get("content-type") || "application/json");
  const cookie = req.headers.get("cookie");
  if (cookie) headers.set("cookie", cookie);
  const origin = req.headers.get("origin");
  if (origin) headers.set("origin", origin);
  return new Request(cleanUrl, { method: req.method, headers, body });
}

export async function GET(req: Request) {
  const auth = await getAuth();
  return auth.handler(toCleanRequest(req));
}

export async function POST(req: Request) {
  const auth = await getAuth();
  const body = await req.text();
  return auth.handler(toCleanRequest(req, body));
}
```

### Schema Drizzle para Better Auth
Las tablas de Better Auth usan `text` como tipo de ID y columnas en camelCase. Crear `lib/schema.ts` con pgTable para: `user`, `session`, `account`, `verification`. Mapear exactamente a las columnas que Better Auth crea (emailVerified, createdAt, updatedAt, etc.).

### Checklist rápido
- [ ] Driver: `postgres` (postgres.js), no `pg`
- [ ] URL: Transaction Pooler (`:6543`), verificada en dashboard
- [ ] `prepare: false` en postgres client
- [ ] Dynamic imports (`await import(...)`) en route handler
- [ ] `export const dynamic = "force-dynamic"` en route
- [ ] `toCleanRequest()` para reconstruir Request limpio
- [ ] Schema Drizzle con tablas de Better Auth
- [ ] `BETTER_AUTH_URL` en Vercel = URL de producción
- [ ] `NEXT_PUBLIC_APP_URL` en Vercel = URL de producción
- [ ] `getSessionCookie` en proxy.ts necesita `cookiePrefix` si se usa prefix custom

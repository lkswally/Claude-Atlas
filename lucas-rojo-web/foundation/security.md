# Security Spec — lucas-rojo-web

**Stack:** Next.js 16 App Router + Vercel + Resend + Cal.com embed
**Scope:** Sitio estático + 1 Route Handler `/api/contact` + embed Cal.com + CV PDF estático
**Sin auth, sin DB, sin pagos, sin UGC**

---

## 1. STRIDE — Threat Model

### Endpoint `/api/contact`

| Amenaza | Categoría | Riesgo | Mitigación |
|---|---|---|---|
| Spam masivo / abuso del endpoint | DoS + costo Resend | Alto | Rate limit por IP (Upstash Redis), honeypot, Turnstile opcional |
| Inyección en el body del email (header injection via `\r\n` en `name`/`email`/`subject`) | Tampering / Injection | Alto | Zod schema estricto, escape de newlines en strings antes de pasar a Resend, usar `react-email` o template fijo |
| Email spoofing del `from` | Spoofing | Medio | `from` hardcodeado server-side (nunca desde el body), SPF/DKIM/DMARC en dominio Resend |
| Enumeración de info por respuestas distintas | Info Disclosure | Bajo | Respuesta genérica `{ ok: true }` siempre; logging server-side |
| Replay attacks / submits duplicados | Tampering | Bajo | Idempotency key opcional; rate limit ya cubre |
| Exfiltración de `RESEND_API_KEY` | Info Disclosure | Crítico | Env var server-only, nunca `NEXT_PUBLIC_*`, no logear |
| Abuso para enviar phishing a terceros (open relay) | Elevation | Alto | `to` hardcodeado al inbox propio, nunca desde body |
| XSS via contenido del mensaje renderizado en el email | Tampering | Medio | Escape HTML en template del email (react-email lo hace por default) |

### Embed Cal.com

| Amenaza | Categoría | Riesgo | Mitigación |
|---|---|---|---|
| Clickjacking del iframe contra el dominio | Spoofing | Bajo | CSP `frame-ancestors 'self'`; el embed es nuestro iframe hacia Cal.com (no al revés) |
| Cal.com comprometido sirve JS malicioso | Tampering | Bajo | Embed en `<iframe>` aislado (no script inline); SRI no aplica a iframes |
| Tracking cross-site via Cal.com | Info Disclosure | Bajo | `Referrer-Policy: strict-origin-when-cross-origin`; documentar en privacy notice |
| Tab-nabbing en links externos del sitio | Spoofing | Bajo | Todo `<a target="_blank">` con `rel="noopener noreferrer"` (enforced en code review) |

### CV PDF estático

| Amenaza | Categoría | Riesgo | Mitigación |
|---|---|---|---|
| PDF con metadata sensible (autor, software, ruta local) | Info Disclosure | Bajo | Sanitizar metadata antes de subir (`exiftool -all=`) |
| Hot-linking desde otros sitios consumiendo bandwidth | DoS | Muy bajo | Vercel CDN absorbe; ignorable |

---

## 2. Headers de Seguridad (`next.config.ts`)

```ts
const securityHeaders = [
  { key: 'X-Content-Type-Options', value: 'nosniff' },
  { key: 'X-Frame-Options', value: 'DENY' },
  { key: 'Referrer-Policy', value: 'strict-origin-when-cross-origin' },
  { key: 'Strict-Transport-Security', value: 'max-age=63072000; includeSubDomains; preload' },
  { key: 'Permissions-Policy', value: 'camera=(), microphone=(), geolocation=(), interest-cohort=()' },
  {
    key: 'Content-Security-Policy',
    value: [
      "default-src 'self'",
      "script-src 'self' 'unsafe-inline' https://app.cal.com https://va.vercel-scripts.com",
      "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com",
      "font-src 'self' https://fonts.gstatic.com data:",
      "img-src 'self' data: blob: https://app.cal.com",
      "frame-src 'self' https://app.cal.com https://cal.com",
      "connect-src 'self' https://app.cal.com https://api.resend.com https://vitals.vercel-insights.com",
      "frame-ancestors 'self'",
      "base-uri 'self'",
      "form-action 'self'",
      "object-src 'none'",
      "upgrade-insecure-requests"
    ].join('; ')
  }
];

module.exports = {
  async headers() {
    return [{ source: '/:path*', headers: securityHeaders }];
  }
};
```

**Notas CSP:**
- `'unsafe-inline'` en `script-src` es lamentable pero Next.js App Router lo necesita para hydration inline. Para eliminarlo: usar nonces via middleware (más complejo, opcional fase 2).
- Si NO se usa Google Fonts (preferir `next/font` self-hosted): quitar `fonts.googleapis.com` y `fonts.gstatic.com`. Recomendado.
- `va.vercel-scripts.com` y `vitals.vercel-insights.com` solo si se activa Vercel Analytics.

---

## 3. Rate Limiting del Form

**Recomendación: Upstash Redis** (no Vercel KV).

**Por qué Upstash sobre Vercel KV:**
- Upstash tiene free tier generoso (10k commands/día) y SDK `@upstash/ratelimit` plug-and-play.
- Vercel KV ahora es marketplace (Upstash por debajo igual) — directo a Upstash evita un layer.
- Latencia comparable; ambos edge-compatible.

**Implementación:**
```ts
import { Ratelimit } from '@upstash/ratelimit';
import { Redis } from '@upstash/redis';

const ratelimit = new Ratelimit({
  redis: Redis.fromEnv(),
  limiter: Ratelimit.slidingWindow(3, '10 m'), // 3 envíos / 10 min / IP
  analytics: true,
});

// En el handler:
const ip = req.headers.get('x-forwarded-for')?.split(',')[0] ?? 'anon';
const { success } = await ratelimit.limit(`contact:${ip}`);
if (!success) return Response.json({ ok: false }, { status: 429 });
```

**Límites sugeridos:**
- 3 envíos / 10 min por IP (form contacto)
- 10 envíos / 1 hora por IP (límite duro diario)

---

## 4. Validación + Anti-spam

### Zod schema
```ts
import { z } from 'zod';

export const contactSchema = z.object({
  nombre: z.string().trim().min(2).max(80).regex(/^[^\r\n]+$/, 'no newlines'),
  email: z.string().trim().toLowerCase().email().max(120),
  empresa: z.string().trim().max(120).regex(/^[^\r\n]*$/).optional(),
  mensaje: z.string().trim().min(10).max(2000),
  // Honeypot — debe venir vacío
  website: z.string().max(0).optional(),
  // Timestamp del render del form (anti-bot que llena instantáneo)
  ts: z.coerce.number().refine(t => Date.now() - t > 3000, 'too fast'),
});
```

### Anti-spam stack
1. **Honeypot field** (`website` hidden via CSS `display:none`) — bots lo llenan, humanos no. Si viene con valor → silenciosamente `return 200` (no revelar detección).
2. **Timestamp gate** — rechazar submits en < 3 segundos del render.
3. **Rate limit** (sección 3).
4. **Cloudflare Turnstile** (opcional, recomendado si spam supera honeypot+ratelimit):
   - Mejor que hCaptcha: invisible, sin tracking, free, mejor UX.
   - Env vars: `TURNSTILE_SITE_KEY` (public), `TURNSTILE_SECRET_KEY` (server).

### Header injection — sanitización Resend
```ts
const safe = (s: string) => s.replace(/[\r\n]/g, ' ').slice(0, 500);
await resend.emails.send({
  from: 'web@tudominio.com',          // hardcoded
  to: 'lucas@tudominio.com',          // hardcoded
  replyTo: safe(data.email),
  subject: `[web] ${safe(data.nombre)}`,
  react: ContactEmail({ ...data }),   // react-email escapa HTML
});
```

---

## 5. Secretos / Env Vars

| Var | Scope | Donde |
|---|---|---|
| `RESEND_API_KEY` | server-only | Vercel env (Production + Preview) |
| `UPSTASH_REDIS_REST_URL` | server-only | Vercel env |
| `UPSTASH_REDIS_REST_TOKEN` | server-only | Vercel env |
| `CONTACT_TO_EMAIL` | server-only | Vercel env (inbox destino) |
| `TURNSTILE_SECRET_KEY` | server-only | Vercel env (si se activa) |
| `NEXT_PUBLIC_TURNSTILE_SITE_KEY` | public | Vercel env (si se activa) |
| `NEXT_PUBLIC_CAL_USERNAME` | public | Vercel env |

**Reglas:**
- `.env.local` en `.gitignore` (verificar).
- `.env.example` commiteado con keys vacías para onboarding.
- Nunca prefijo `NEXT_PUBLIC_` salvo lo necesario (públicas).
- Rotación: `RESEND_API_KEY` cada 90 días o ante sospecha.
- No logear ningún env var (incluido en errores).

---

## 6. OWASP Top 10 — Aplicabilidad

| Risk | Aplica | Mitigación |
|---|---|---|
| **A01 Broken Access Control** | N/A | Sin auth, sin recursos privados |
| **A02 Cryptographic Failures** | Parcial | HTTPS forzado (HSTS); sin datos sensibles persistidos |
| **A03 Injection** | **SÍ** | Zod en `/api/contact`; sanitización newline para headers SMTP; react-email escapa HTML |
| **A04 Insecure Design** | SÍ | Este threat model existe; honeypot + ratelimit por diseño |
| **A05 Security Misconfiguration** | **SÍ** | Headers (sección 2); CSP estricta; no source maps en prod (verificar `productionBrowserSourceMaps: false`); 404 genérico |
| **A06 Vulnerable Components** | SÍ | `npm audit` en CI; Dependabot/Renovate activado; `lockfile-lint` en pipeline |
| **A07 Auth Failures** | N/A | Sin auth |
| **A08 Data Integrity Failures** | Parcial | Pin de actions a SHA en GitHub Actions (si hay CI); SRI no aplica a iframes |
| **A09 Logging Failures** | SÍ | Loguear submits exitosos/fallidos del form (sin datos personales completos — solo IP truncada + timestamp + status); Vercel Logs es suficiente |
| **A10 SSRF** | N/A | El server no hace fetch de URLs del usuario |

### Checklist pre-deploy (Fase 4)
- [ ] `npm audit --production` sin criticals
- [ ] `npx lockfile-lint --allowed-hosts npm --allowed-schemes https: --type npm --path package-lock.json`
- [ ] Headers verificados con `curl -I` o securityheaders.com (target: A+)
- [ ] CSP probada (sin `Refused to load` en consola)
- [ ] Source maps NO accesibles en prod (`curl https://dominio.com/_next/static/.../page.js.map` → 404)
- [ ] PDF del CV con metadata sanitizada (`exiftool cv.pdf` no expone path local)
- [ ] Rate limit probado (4to submit en 10min → 429)
- [ ] Honeypot probado (submit con `website` no vacío → silently ok, sin email)
- [ ] Env vars NO en bundle cliente (`grep -r "RESEND" .next/static/` vacío)
- [ ] `rel="noopener noreferrer"` en todos los `target="_blank"`

---

## 7. GDPR / Aviso Legal

**Datos personales recolectados:**
- Form: nombre, email, empresa (opcional), mensaje
- Cal.com: gestiona sus propios datos al agendar (su política aplica)
- Vercel Analytics (si se activa): IP anonimizada, sin cookies por default

**Mínimo legal a incluir:**

### Texto debajo del form (link a /privacidad)
> Al enviar este formulario aceptás que use tu email para responderte. No comparto tus datos con terceros ni los uso para marketing. Más info en [Privacidad](/privacidad).

### Página `/privacidad` (contenido mínimo)
- **Responsable:** Lucas Rojo, contacto: `lucas@dominio.com`
- **Datos que recolecto:** los del form de contacto; los de Cal.com al agendar (gestionados por Cal.com Inc., ver su política)
- **Finalidad:** responder consultas, gestionar reuniones
- **Base legal:** consentimiento (GDPR Art. 6.1.a) e interés legítimo (responder consultas profesionales)
- **Retención:** emails archivados en mi inbox indefinidamente; baja a pedido
- **Derechos:** acceso, rectificación, supresión — escribir a `lucas@dominio.com`
- **Terceros procesadores:** Resend (email), Vercel (hosting), Cal.com (agendado), Upstash (rate limiting — solo IP truncada, 10 min retention)
- **Cookies:** ninguna propia. Cal.com embed puede setear las suyas (documentar)
- **Transferencias internacionales:** Vercel y Resend operan desde USA — SCC aplicables

### Cookie banner — ¿necesario?
- Si NO se usan cookies propias ni Vercel Analytics con cookies → **no es obligatorio banner** bajo GDPR (suficiente con aviso en /privacidad).
- Si se activa Vercel Analytics → mantener modo sin cookies (default), no requiere banner.
- Cal.com embed: técnicamente carga en iframe terceros → mencionar en /privacidad es suficiente; algunos consideran necesario consent. Conservador: cargar el embed solo tras click ("Cargar agenda") — patrón consent-by-action.

---

## Resumen — Top 5 controles obligatorios pre-deploy

1. **Headers + CSP** estrictos en `next.config.ts` (sección 2)
2. **Rate limit** Upstash 3/10min en `/api/contact`
3. **Zod + honeypot + sanitización newline** en validación del form
4. **Env vars** server-only, `from`/`to` hardcoded en Resend (no open relay)
5. **Página /privacidad** publicada + link bajo el form

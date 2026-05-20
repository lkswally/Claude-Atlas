# Content Spec v3 — Lucas Rojo · Editorial operativo cálido

**Reemplaza a content.md v2.** Esta es la fuente de verdad para el rebuild visual completo.

---

## Dirección visual

**"Editorial operativo cálido"** — fondo cream + ink + acento verde inglés, con cian solo como detalle puntual donde aporte profundidad tech sin ensuciar la paleta.

### Paleta
| Token | Hex | Uso |
|---|---|---|
| `--paper` | `#F4F1EA` | Fondo principal warm cream |
| `--paper-soft` | `#EBE7DD` | Surface alternativa |
| `--ink` | `#15140F` | Texto principal warm black |
| `--ink-muted` | `#6B6760` | Texto secundario |
| `--ink-faded` | `#9B968C` | Captions, metadatos |
| `--rule` | `#D6CFC1` | Líneas separadores |
| `--accent` | `#1F4D3F` | **Verde inglés** — único acento principal |
| `--accent-soft` | `#E7EDE8` | Bg del acento, chips |
| `--dark` | `#1A1814` | Bloques dark alternados |
| `--dark-paper` | `#252119` | Surface dentro de dark |
| `--dark-ink` | `#F4F1EA` | Texto en bloques dark |
| `--tech` | `#1FB6C7` | **Cian sutil** — SOLO para detalles tech contenidos (línea decorativa, dot de status beta, etc.) — máximo 1 uso por sección |

### Tipografía
- **General Sans** (Indian Type Foundry — Fontshare) — display + body, pesos 400/500/600. No Geist Sans.
- **Newsreader Italic** (Google Fonts) — solo italic accent puntual, máximo 1-2 palabras por bloque
- **Geist Mono** — años, métricas, captions caps (mantener)

### Stack motion
Framer Motion + Lenis. Conservar: canvas de problema (redibujado en cream/ink), línea de método dibujándose, fade-ups suaves. Eliminar: magnetic CTA, system diagram del hero, pulse rings, glow del cian.

---

## Retrato

Path esperado: `D:\ProyectosIA\ProyectosClaude\lucas-rojo-web\web\public\portrait.png`
Si no existe al build: usar **placeholder SVG editorial** — silueta abstracta + monograma "LR" en ink sobre paper, sin "foto pendiente" en texto visible.
Componente `<Portrait />` debe permitir reemplazo sin tocar layout.

Tratamiento visual:
- En Hero: lado derecho, máscara orgánica (no rectángulo duro), 480-560px desktop / full-width contenido mobile
- En /sobre: composición editorial integrada con texto
- En /recorrido: opcional — versión más pequeña como sello

---

## Arquitectura

| Ruta | Estado |
|---|---|
| `/` | Home con scroll narrativo |
| `/sobre` | Perfil extendido + retrato |
| `/servicios` | 6 servicios con detalle simplificado + 3 paquetes |
| `/recorrido` | Trayectoria con Fisconexo/Bookhap correctos |
| `/laboratorio` | Reemplaza `/diagnostico` — Career OS (beta activa) + Diagnóstico 360 (próximamente) + Asistente (idea) |
| `/contacto` | Form + Cal.com |
| `/aviso-legal` | Disclaimer completo |
| `/privacidad` | Política básica |

**Header nav:** Sobre · Servicios · Lab · Conversemos *(sin CTA pill)*

---

## HOME

### Hero (bloque paper)
- Eyebrow chip mono caps: `MENDOZA, AR · ASESORÍA INDEPENDIENTE`
- Display sans (General Sans 500): *"Ayudo a empresas a ordenar procesos, mejorar la experiencia del cliente y adoptar herramientas digitales — sin complicar más la operación."*
- Italic en "ordenar" con Newsreader Italic
- 2 CTAs:
  - Primary (verde inglés fill): `Agendar una conversación`
  - Secondary (underline): `Ver cómo puedo ayudar →`
- Lado derecho: Retrato editorial
- Strip inferior sutil: 4 datos compactos sin counters animados — `10+ años en software` · `4 productos acompañados` · `Mendoza · LATAM` · `Disponible 2026`

### Sección Problema (bloque dark)
- Eyebrow: `EL PROBLEMA`
- Título: *"Cuando la empresa crece, la operación deja de caber en la cabeza de pocas personas."*
- Bajada corta (1 línea)
- Lista visual horizontal:
  - chats que se pierden
  - planillas paralelas
  - reclamos que se repiten
  - herramientas usadas sin criterio
- Conservar canvas de nodos caos→orden pero redibujado en `--dark-ink` sobre `--dark`, con tinte `--accent` muy contenido.

### Sección Recorrido (bloque paper)
- Eyebrow: `RECORRIDO`
- Lead paragraph: *"Vengo de estar dentro de operaciones reales en empresas tecnológicas. Trabajé cerca de soporte, producto, operaciones, administración, finanzas y equipos técnicos."*
- Timeline editorial vertical compacta:
  - `2014 — presente` · **Reyesoft** · Operaciones & Project Management
  - `2024 — presente` · **Fisconexo** · Discovery & service design
  - `2023 — presente` · **Bookhap** · Captación · capacitación · OTAs
  - `2014 — presente` · **Saldoar** · Soporte · Ventas · Back Office
  - `2015 — 2017` · **Multinexo** · Soporte
  - `Ecosistema tech San Rafael` · Polo de Innovación Sur de Mendoza
- Disclaimer integrado al final con tono natural y muted:
  *"Esta es una web personal. Las empresas y productos mencionados forman parte de mi recorrido profesional y pertenecen a sus respectivos titulares."*

### Sección Cómo trabajo (bloque paper)
- Eyebrow: `MÉTODO`
- Sin cards. Cinco verbos en bloques horizontales editoriales:
  - **Entiendo** — el contexto, sin asumir
  - **Ordeno** — lo que está disperso o tácito
  - **Documento** — para que no dependa de personas
  - **Mido** — lo que importa, no todo
  - **Automatizo** — cuando tiene sentido, no por moda
- Línea horizontal cian sutil conecta los 5 verbos al scroll (conservar animación draw existente, repintada).

### Sección Servicios (bloque dark contenido)
- Eyebrow: `SERVICIOS`
- Título: *"Seis frentes donde acompaño."*
- Formato acordeón editorial. Cada servicio:
  - Título (24-28px)
  - Bajo título cerrado: 1 línea pitch
  - Al abrir: 3 mini-bloques `Problema` / `Cómo ayudo` / `Resultado esperado` — max 2 líneas cada uno
- Los 6 servicios:
  1. **Procesos operativos** — *Problema:* Cada cambio de persona desarma el flujo. *Cómo ayudo:* Mapeo, documento y diseño los procesos críticos. *Resultado:* La operación deja de depender de personas.
  2. **Experiencia del cliente (CX)** — *Problema:* Las quejas se repiten pero nadie las consolida. *Cómo ayudo:* Audito el journey y diseño procesos de atención y postventa. *Resultado:* Una experiencia consistente y medible.
  3. **Orden financiero operativo** — *Problema:* Fin de mes siempre es caos. *Cómo ayudo:* Ordeno los procesos de facturación, cobranza y conciliación. *Resultado:* Información clara, sin reemplazar al contador.
  4. **People / RRHH** — *Problema:* Onboardings improvisados y evaluaciones inconsistentes. *Cómo ayudo:* Documento el ciclo del colaborador completo. *Resultado:* El equipo crece sin perder criterio.
  5. **IA, automatización y vibe coding** — *Problema:* Herramientas que se prueban y no se quedan. *Cómo ayudo:* Auditoría del stack, roadmap por ROI, casos acotados. *Resultado:* Tiempo real ahorrado, no PowerPoints.
  6. **Identidad comercial / registro de marca (operativo)** — *Problema:* Nombre, dominio y redes desalineados antes de registrar. *Cómo ayudo:* Ordeno la identidad y preparo la documentación. *Resultado:* Llegás al abogado con todo listo. *Aclaración chip:* "No brindo asesoramiento legal. Acompaño desde lo operativo."

CTA debajo: `Ver detalles y paquetes →` → /servicios

### Sección Laboratorio (bloque paper)
- Eyebrow: `LABORATORIO`
- Lead: *"Productos y herramientas que estoy construyendo en paralelo a la asesoría."*
- 3 cards editoriales (no premium glow, más planas/elegantes):

  **1. Career OS — Búsqueda laboral asistida** *(BETA activa)*
  - Badge: `BETA` (verde inglés + dot pulsante muy sutil)
  - Pitch: *"Encontrá puestos que te interesan con una búsqueda asistida."*
  - Bajada: *"Completá qué tipo de trabajo estás buscando y recibí por correo oportunidades filtradas según rol, ubicación, modalidad, seniority e idioma."*
  - CTA: `Buscar oportunidades` → abre form expandible inline o navega a `/laboratorio#career-os`
  - Aclaración pequeña: *"No garantiza empleo ni reemplaza tu búsqueda activa. Te ayuda a ahorrar tiempo y priorizar."*

  **2. Diagnóstico Digital 360** *(próximamente, honesto)*
  - Badge: `PRÓXIMAMENTE`
  - Pitch: *"Una herramienta para revisar sitios web desde UX, SEO, claridad comercial y conversión."*
  - Bajada: *"Estoy preparando esto. Si querés probarla cuando esté lista, dejame tu email."*
  - CTA: `Avisame cuando esté lista` (waitlist)

  **3. Asistente de Lucas** *(idea)*
  - Badge: `IDEA · explorando`
  - Pitch: *"Un asistente con mi forma de pensar operaciones, para consultas rápidas sin agendar."*
  - Sin CTA — solo texto. Honesto.

### Sección CTA final (bloque dark)
- Título grande sans: *"Si tu empresa está creciendo, pero la operación se está volviendo difícil de sostener — conversemos."*
- Botón único: `Agendar una conversación`
- Texto pequeño debajo: *30 minutos · sin compromiso · remoto*

---

## /sobre

- Eyebrow: `SOBRE`
- Display: *"Generalista por elección, operativo por oficio."*
- Layout dos columnas: retrato grande izquierda + texto derecha
- 3 párrafos cortos (los del v2, pulidos):

  Llevo más de una década dentro de la industria del software. Empecé resolviendo tickets de soporte y terminé liderando áreas de operaciones, soporte, marketing y producto en equipos multidisciplinarios. Ese recorrido —de la línea de fuego a la dirección operativa— me enseñó que el problema casi nunca está donde parece, y que la respuesta casi siempre es un proceso bien diseñado.

  No soy fundador ni dueño de las empresas en las que trabajé. Soy alguien que entra, entiende cómo funciona el negocio, encuentra los cuellos de botella reales y ayuda a destrabarlos. Diseño procesos, documento criterios, mido lo que importa y dejo el equipo en mejor estado del que lo encontré.

  Hoy combino esa mirada operativa con un interés activo en IA, automatizaciones y *vibe coding* — no como buzzwords, sino como herramientas concretas que, bien aplicadas, ahorran horas reales a equipos reales. Trabajo desde Mendoza con empresas de habla hispana.

- **En qué soy fuerte:** ordenar lo desordenado · documentar lo tácito · medir lo que no se medía · acompañar adopciones tecnológicas sin romper al equipo.
- **En qué no:** reemplazar a un contador, a un abogado o a un especialista vertical. Sé hasta dónde llega mi alcance.

- Certificaciones (lista compacta, no cards): Project Manager · Full Stack JS/Node · Big Data & Data Analytics · Lean UX · PHP Fullstack · Python (Citibank)

---

## /servicios

Misma estructura que home pero **cada servicio ocupa una "section block" full-width** con:
- Eyebrow `SERVICIO 0X`
- Título grande
- Problema / Cómo ayudo / Resultado en 3 columnas o stacked
- Box pequeño "También trabajo": detalles concretos (3-4 bullets, no extensos)

Después de los 6 servicios: **Paquetes** (sin grid, formato bloques editoriales horizontales):
- **A — Diagnóstico Operativo** · 2 semanas · remoto · inversión a consultar
- **B — Implementación Acompañada** · 3 meses · remoto + sesiones quincenales · inversión a consultar
- **C — Advisor Mensual** · mínimo 3 meses · 2 reuniones mensuales · inversión a consultar

CTA final: `Conversemos sobre tu caso →`

---

## /recorrido

Misma narrativa del home pero expandida:
- Eyebrow + título + bajada
- Lista completa con detalle:
  - Reyesoft (2014-presente) · 3 líneas de rol
  - Saldoar (desde 2014) · contexto + aprendizaje clave
  - Multinexo (2015-2017) · contexto
  - Bookhap (desde 2023) · link discreto a [bookhap.com](https://bookhap.com/) abre en nueva pestaña
  - Fisconexo (desde 2024) · link discreto a [fisconexo.com](https://fisconexo.com/)
  - Ecosistema tech San Rafael
- Disclaimer integrado y prominente al final
- Sin métricas inventadas

---

## /laboratorio

Reemplaza `/diagnostico`. Tres secciones, una por proyecto:

### Career OS — sección expandida con form
- Hero del proyecto (título + bajada + badge BETA)
- Explicación honesta del flujo (3-4 líneas)
- **Formulario** con campos:
  - Nombre *(requerido)*
  - Email *(requerido)*
  - Puesto buscado *(requerido)*
  - País o región *(requerido)*
  - Modalidad *(select: Remoto · Híbrido · Presencial · Indistinto)*
  - Seniority *(select: Junior · SemiSenior · Senior · Lead · Director)*
  - Nivel de inglés *(select: Básico · Intermedio · Avanzado · Nativo)*
  - Comentarios *(textarea, opcional)*
  - Honeypot oculto + timestamp gate
  - Opt-in privacidad
- Botón: `Buscar oportunidades`
- Aclaración pequeña: *"No garantiza empleo ni reemplaza tu búsqueda activa."*
- Mensaje de éxito honesto: *"Recibimos tu pedido. Estamos activando las primeras búsquedas en beta — te escribimos en breve."*

### Diagnóstico Digital 360 — solo waitlist
- Sección compacta: título, bajada, input email + botón `Avisame cuando esté lista`
- Sin promesas de 60 segundos, sin PDF, sin score.

### Asistente de Lucas — solo descripción
- Tres líneas honestas. Sin form.

---

## /contacto

- Form actual (mantener) con copy más humano: *"Contame qué te está pasando y vemos si tiene sentido conversar."*
- Cal.com embed
- Email visible: lksrojo86@gmail.com
- LinkedIn

---

## /aviso-legal

Mantener contenido v2 pero ajustar:
- Quitar referencia a "Fiscoflex" — usar "Fisconexo"
- Mencionar Career OS: *"Career OS es una herramienta beta de búsqueda laboral asistida. Los datos enviados se procesan para generar reportes personalizados; no se comparten con terceros más allá del proveedor de envío de email."*

---

## API endpoints

### `POST /api/career-os`
- Valida payload con zod
- Honeypot + timestamp gate >3s
- Rate limit (TODO comment para Upstash)
- **Llama a webhook n8n** vía env var `N8N_CAREEROS_WEBHOOK_URL` (privado, server-side only)
- Si la env var no está definida → loguea y devuelve success simulado *(modo dev / pre-producción)*
- Responde `{ ok: true, message: "Recibimos tu pedido" }`
- **Nunca expone la URL del webhook al cliente**

### `POST /api/diagnostico-waitlist`
- Solo email + zod + honeypot
- TODO Resend, por ahora console.log

### `POST /api/contact`
- Mantener actual

---

## Cambios concretos al código existente

### Eliminar
- `components/sections/lo-que-hago.tsx` (sección entera — redundante con servicios)
- `components/sections/metricas.tsx` (eliminar counters, datos pasan a strip del hero estático)
- `useMagneticEffect` del hero
- `system diagram` SVG del hero
- `Instrument Serif` de toda referencia (font + class)
- Tokens cian `#00D4FF` reemplazados por `--accent` verde inglés
- Variable de cian conservada solo como `--tech` para detalles puntuales

### Renombrar
- `app/diagnostico/page.tsx` → `app/laboratorio/page.tsx` + redirect 301 (en next.config)
- `components/sections/diagnostico-teaser.tsx` → `components/sections/laboratorio.tsx`
- `components/sections/herramientas.tsx` → fusionar con laboratorio o eliminar
- `components/sections/metricas.tsx` → eliminar
- `components/sections/lo-que-hago.tsx` → eliminar

### Crear
- `components/shared/portrait.tsx` con placeholder SVG editorial
- `components/sections/laboratorio.tsx` con 3 cards Career OS + D360 + Asistente
- `app/laboratorio/page.tsx` con form Career OS completo
- `app/api/career-os/route.ts` con validación + webhook stub
- `lib/fonts.ts` actualizado con General Sans + Newsreader Italic + Geist Mono

### Modificar
- `app/globals.css` con paleta nueva + tokens motion (conservar)
- `app/layout.tsx` body color por defecto `--paper` `--ink`
- `app/page.tsx` con nuevo orden y sin secciones eliminadas
- Todos los componentes de sección con paleta nueva
- `next.config.ts` redirect `/diagnostico → /laboratorio`
- `sitemap.ts` actualizar rutas
- `llms.txt` y `llms-full.txt` reescribir con productos correctos y posicionamiento nuevo

---

## Criterios de aceptación

- En 5 segundos se entiende quién es Lucas y qué hace
- No parece dashboard ni template SaaS
- Tipografía sans moderna, legible, sin saturar serif
- Retrato editorial integrado (placeholder si no hay archivo)
- Servicios entendibles en 1 lectura
- Career OS funciona como beta activa (form → API → mock OK)
- Diagnóstico 360 sin promesas falsas
- Fisconexo (no Fiscoflex), Bookhap correctos
- Disclaimer integrado natural
- Mobile excelente
- Build limpio
- Lighthouse no baja respecto a v2.1

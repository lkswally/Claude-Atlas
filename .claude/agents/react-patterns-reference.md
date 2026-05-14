---
name: react-patterns-reference
description: Referencia de patrones React 19, Next.js 15/16, Tailwind 4, Zustand, TanStack Query. Cargado por frontend-developer cuando necesita implementar estos patrones.
---

# React Patterns Reference

## Patrones modernos (React 19 / Next.js 15 / Tailwind 4)

### React 19 — No usar anti-patrones anteriores

```typescript
// React 19: escribir código normal, el compilador optimiza
const value = compute(a, b);
const handler = () => doSomething();

// use() hook — leer Promises y Context directamente en render
import { use, Suspense } from 'react';

function UserProfile({ userPromise }: { userPromise: Promise<User> }) {
  const user = use(userPromise); // suspende hasta resolver
  return <div>{user.name}</div>;
}
// Siempre envolver en Suspense:
<Suspense fallback={<Skeleton />}>
  <UserProfile userPromise={fetchUser(id)} />
</Suspense>

// useActionState — estado de Server Actions en formularios
import { useActionState } from 'react';

const [state, action, isPending] = useActionState(serverAction, { error: null });
<form action={action}>
  <input name="email" type="email" />
  <button disabled={isPending}>{isPending ? 'Enviando...' : 'Enviar'}</button>
  {state.error && <p className="text-red-500">{state.error}</p>}
</form>
```

### Next.js 15 — Server Actions, server-only y streaming

```typescript
// Server Actions — "use server" como primera línea
'use server';
import { revalidatePath } from 'next/cache';

export async function createPost(formData: FormData) {
  const title = formData.get('title') as string;
  await db.insert(posts).values({ title });
  revalidatePath('/posts');
}

// server-only — evitar que código de servidor se importe en el cliente
import 'server-only'; // lanza error de build si se importa en Client Component

// Route Handler (app/api/nombre/route.ts)
export async function GET(request: Request) {
  const { searchParams } = new URL(request.url);
  const id = searchParams.get('id');
  return Response.json({ data: await fetchData(id) });
}

// Streaming con Suspense (cargar partes de la página independientemente)
export default async function Page() {
  return (
    <main>
      <h1>Dashboard</h1>
      <Suspense fallback={<StatsLoading />}>
        <Stats />  {/* Server Component async — carga sin bloquear la página */}
      </Suspense>
      <Suspense fallback={<FeedLoading />}>
        <Feed />
      </Suspense>
    </main>
  );
}
```

### Tailwind 4 — Reglas de uso

```typescript
// NO usar var() en className — Tailwind 4 no interpola CSS variables en utilidades
// Para CSS variables, usar el atributo style
<div style={{ color: 'var(--color-primary)' }} />

// O usar clases Tailwind directas
<div className="text-blue-600" />

// cn() SOLO para condicionales — no para strings estáticos
const cls = cn(
  'flex items-center gap-2',
  { 'opacity-50 cursor-not-allowed': disabled },
  isActive && 'bg-blue-100',
);
```

### TypeScript — Const Types en vez de enums

```typescript
// Const Types: objeto as const → derivar tipo automáticamente
const STATUS = {
  Active: 'active',
  Inactive: 'inactive',
  Pending: 'pending',
} as const;

type Status = typeof STATUS[keyof typeof STATUS]; // 'active' | 'inactive' | 'pending'

// Usar en componentes con autocompletado completo sin overhead JS
function Badge({ status }: { status: Status }) {
  const colors = {
    [STATUS.Active]: 'bg-green-100 text-green-800',
    [STATUS.Inactive]: 'bg-gray-100 text-gray-800',
    [STATUS.Pending]: 'bg-yellow-100 text-yellow-800',
  };
  return <span className={colors[status]}>{status}</span>;
}
```

## Patrones de implementación

### State management con Zustand (preferido sobre Redux/Context para state complejo)
```typescript
// Simple, sin boilerplate, sin providers
const useStore = create<State>((set) => ({
  items: [],
  addItem: (item) => set((s) => ({ items: [...s.items, item] })),
}));
// Usar en cualquier componente sin wrapper
const items = useStore((s) => s.items);

// Zustand 5 — useShallow para seleccionar múltiples campos sin re-renders extra
import { useShallow } from 'zustand/react/shallow';

// Con useShallow — solo re-render si count o name cambian de valor
const { count, name } = useStore(useShallow((s) => ({ count: s.count, name: s.name })));
```
Usar Zustand cuando: carrito, UI state (modals, sidebar), filtros. NO usar para server state (usar TanStack Query).

### Data fetching con TanStack Query (para datos del servidor)
```typescript
const { data, isLoading, error } = useQuery({
  queryKey: ['users', filters],
  queryFn: () => api.users.list(filters),
});
// Mutations con invalidación automática
const mutation = useMutation({
  mutationFn: api.users.create,
  onSuccess: () => queryClient.invalidateQueries({ queryKey: ['users'] }),
});
```
TanStack Query maneja: caching, refetch, pagination, optimistic updates, loading/error states. NO duplicar esta lógica manualmente.

### Forms con react-hook-form + Zod
```typescript
const schema = z.object({ email: z.string().email(), name: z.string().min(2) });
const form = useForm<z.infer<typeof schema>>({ resolver: zodResolver(schema) });
```
El schema Zod puede compartirse con el backend (packages/types/ en monorepo) para validación end-to-end.

### tRPC client (cuando el backend lo usa)
```typescript
// El tipo se importa directamente — autocompletado + validación end-to-end
import type { AppRouter } from '@proyecto/api';
const trpc = createTRPCReact<AppRouter>();
// Usar con TanStack Query automáticamente
const { data } = trpc.getUser.useQuery({ id: '123' });
```

### Selección de herramientas
| Necesidad | Herramienta | NO usar |
|-----------|-------------|---------|
| UI state (modals, sidebar, theme) | Zustand | Context (re-renders), Redux (overkill) |
| Server state (API data) | TanStack Query | useEffect + useState (manual, sin cache) |
| Forms con validación | react-hook-form + Zod | Controlled inputs manuales (performance) |
| Animaciones simples (hover, fade, toggle) | CSS transitions / Tailwind animate | JS animations (innecesario) |
| Animaciones React UI (mount/unmount, layout, gestures) | Framer Motion | CSS (limitado para mount/unmount) |
| Timeline complejo, scroll pin, SplitText, SVG morph | GSAP (ver `better-gsap-reference.md`) | Framer Motion (no tiene timeline real ni pinning) |
| Listas infinitas | TanStack Query + useInfiniteQuery | Pagination manual con offset |

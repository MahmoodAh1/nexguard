# NexGuard — Frontend

The enterprise SOC console: a premium dark-theme Next.js 15 app (App Router,
React 19, TypeScript, Tailwind v4, TanStack Query, Framer Motion, Recharts).

## Quickstart

```bash
cp env.example .env.local     # point NEXT_PUBLIC_API_URL at the backend
npm install
npm run dev                    # http://localhost:3000

npm run typecheck              # tsc --noEmit
npm run test                   # vitest
npm run build                  # production build
```

Sign in with the demo credentials seeded by `nexguard seed` (shown on the login
screen).

## Structure

```
src/
  app/
    (auth)/login        sign-in (split-panel)
    (app)/              authenticated shell + Executive Dashboard
    layout.tsx          fonts, providers, metadata
    globals.css         design tokens (Tailwind v4 @theme)
  components/           UI primitives + SOC components (alerts table, report drawer…)
  lib/                  api client, auth context, WebSocket hook, query hooks, types
```

## Design

Restrained CrowdStrike/Sentinel-style dark theme: deep slate surfaces, one calm
interactive blue, semantic severity colors (critical/high/medium/low), Inter for
UI and JetBrains Mono for data. Live updates stream over a resilient WebSocket.

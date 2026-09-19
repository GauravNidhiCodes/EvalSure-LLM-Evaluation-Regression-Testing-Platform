# EVALSURE web dashboard

Next.js App Router UI for EVALSURE.

For full setup (API, auth, Docker, env vars), see the **repository root** [README.md](../../README.md) and [docs/quickstart.md](../../docs/quickstart.md).

## Local development

```bash
cp .env.example .env.local
# NEXT_PUBLIC_API_URL=http://localhost:8000
npm install
npm run dev
```

Open http://localhost:3000 → `/login` or `/register`.

## Scripts

| Command | Purpose |
|---------|---------|
| `npm run dev` | Dev server (Turbopack) |
| `npm test` | Unit tests (compare + auth helpers) |
| `npm run lint` | Next.js ESLint |
| `npm run build` | Production build |
| `npm start` | Serve production build |

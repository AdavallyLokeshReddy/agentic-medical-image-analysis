# Frontend

Next.js (static export) client for the governed head-CT workflow API. See `../DEPLOY.md`.

```
npm ci
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000 npm run dev   # dev falls back to localhost:8000
npm run lint && npx tsc --noEmit && npm run build
```

Structure: `src/api` (the only network layer, typed per real route), `src/features` (viewer, workflow, workspace, governance),
`src/hooks`, `src/components`, `src/app` (routes: `/`, `/cases`, `/workspace?case=`, `/governance`, `/report?case=`).

Design rule: every stage and panel declares its provenance (live / not exposed / unavailable). Nothing is fabricated.

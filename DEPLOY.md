# Deploying the demo

Architecture: **static Next.js frontend** (`frontend/`, `output: "export"`) → **FastAPI** (`backend/`).
No model runs in the deployed API; the UI states this instead of faking results.

## 1. API (Render, free tier)
1. Render → New → Blueprint → select this repo (uses `render.yaml`; installs `requirements-api.txt`, no PyTorch).
2. Set `CORS_ORIGINS` to the frontend origin (comma-separated for several). Never `*`.
3. Check `https://<api>/health` and `https://<api>/governance/status`.

Caveats: uploads live on ephemeral disk and the case registry is in memory, so they vanish on restart/sleep.
Free instances sleep when idle — open `/health` a few minutes before the demo.

## 2. Frontend (Vercel / Netlify / Cloudflare Pages)
- Root directory: `frontend`; build `npm run build`; output `out/`.
- Env var **`NEXT_PUBLIC_API_BASE_URL`** = the API URL (no trailing slash). It is inlined at build time, so
  redeploy after changing it. Without it a production build shows "Backend URL not configured".
- Then add the resulting frontend origin to the API's `CORS_ORIGINS`.

## 3. Local run
```
pip install -r requirements-api.txt && cd backend && uvicorn main:app --port 8000
cd frontend && npm ci && npm run dev        # http://localhost:3000
python scripts/make_synthetic_ct.py /tmp/ct  # synthetic phantom, no patient data
```
Optional: `PORT`-style full model support needs `requirements.txt`, the external `skp` code and weights (see README).
Optional audit view: set `DATABASE_URL` to a PostgreSQL instance.

## 4. Demo script (≈5 min)
1. Overview: backend online, "model is not the system", what the API exposes vs library-only.
2. Cases → New case → Workspace.
3. Upload the synthetic CT (or a real series) → watch progress, validation, preprocessing, preview.
4. Right panel: stage-by-stage provenance — live vs "not exposed". Open Orchestrator plan: safety contract + task graph (planned, not executed).
5. Governance: tool registry metadata and the honest "not exposed — and why".
6. Case report → print/save PDF. Audit tab shows "unavailable" without PostgreSQL.

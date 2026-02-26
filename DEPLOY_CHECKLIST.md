# Deploy Checklist (Render + Vercel)

This checklist gets your app to a public URL with the smallest number of manual steps.

## 1) Push two repos to GitHub

Backend repo (`poker-api-bisixiang`):
- directory: `Poker/`
- must include: `main.py`, `db.py`, `requirements.txt`, `render.yaml`

Frontend repo (`poker-tournaments-bisixiang`):
- directory: `Poker/poker-frontend/`
- must include: `app/`, `lib/`, `package.json`, `next.config.ts`

## 2) Deploy backend on Render (Blueprint)

1. In Render, click `New` -> `Blueprint`.
2. Select backend repo `poker-api-bisixiang`.
3. Render detects `render.yaml` and creates:
   - web service: `poker-api-bisixiang`
   - postgres: `poker-postgres-bisixiang`
4. Click `Apply`.
5. Wait for deploy success.
6. Open:
   - `https://<your-render-domain>/health`
   - `https://<your-render-domain>/api-docs`

## 3) Deploy frontend on Vercel

1. In Vercel, click `Add New...` -> `Project`.
2. Import repo `poker-tournaments-bisixiang`.
3. Set env var:
   - `BACKEND_API_URL=https://<your-render-domain>`
4. Deploy.
5. Open:
   - `https://<your-vercel-domain>/tournaments`

## 4) Lock backend CORS to your frontend domain

In Render web service -> `Environment`:
- Set `FRONTEND_ORIGINS=https://<your-vercel-domain>`
- Redeploy backend

## 5) Final validation

Open these URLs:
- Frontend: `https://<your-vercel-domain>/`
- Frontend list: `https://<your-vercel-domain>/tournaments`
- Backend docs: `https://<your-render-domain>/api-docs`

If frontend shows backend request errors:
- confirm Vercel env var `BACKEND_API_URL` uses `https://...` (not `http://`, not localhost)
- confirm Render service is healthy and not sleeping/cold-start failing

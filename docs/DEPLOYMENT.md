# Zero-payment deployment plan

## Never enable billing
Use free-tier plans and quotas ONLY. Free services can stop when limits are reached. No domain purchase is necessary.

## 1. GitHub
Create an empty repository named `ClinicalTrial-Matcher`, upload the contents of the provided ZIP, or initialize Git and push. Keep `.env` private.

## 2. Cloudflare Pages
- Connect your GitHub repo.
- Framework: React/Vite; project directory: `frontend`.
- Build command: `npm run build`.
- Output: `dist`.
- Environment variable: `VITE_API_BASE_URL=https://<your-render-service>.onrender.com`.
- Free `pages.dev` hostname. This is a static frontend.

## 3. Render Free
- Create a Web Service, connect the same repository.
- Root directory: `backend`.
- Install command: `pip install -r requirements.txt`.
- Start command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`.
- Select the **Free** instance.
- Set `CORS_ORIGINS=https://<your-pages-site>.pages.dev` (use the exact URL).
- Keep `ENABLE_LIVE_AI=false` on the public service; replay and live public registry search remain available.
- Do not set the Gemini API key on a public-facing service until access controls, rate limits, and usage limits are proven.
- Render free can spin down and does not preserve SQLite files or runtime changes. Bundled fixture JSON is read-only.

## 4. Local live agent demonstration (optional)
- Obtain a *free-tier* Gemini API key from Google AI Studio, without linking a paid billing project.
- `cp .env.example .env`, put key inside local `.env`, then load it into the backend process.
- Enable `ENABLE_LIVE_AI=true` locally, not on the publicly accessible default service. Set a strong random `LIVE_AI_ACCESS_TOKEN` (at least 16 characters) and enter that token in the UI when invoking authorized local model calls. This is a prototype access gate, not production-grade authentication.
- Use synthetic patients only. Google may use free-tier requests to improve its services.
- Keep MAX_ASSESSMENTS low and stop rather than upgrade after quota errors.
- Start backend and frontend locally. Use `Live registry`, search, then `Run eligibility + skeptic`.

## 5. Offline demo
The React application includes a versioned synthetic replay snapshot; it works for demo viewing even if Render, the model provider, or ClinicalTrials.gov are unavailable. Replay is visibly labeled throughout and never presented as measured live agent accuracy.

## Checks
1. `/health` returns status `ok`.
2. `/api/v1/demo/cases` returns synthetic fixtures.
3. React loads the replay with no external services.
4. Live public search returns official NCT identifiers when registry is available.
5. Unapproved public model inference is disabled by default.

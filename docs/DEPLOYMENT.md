# Deployment Guide: Railway + Vercel

This project is prepared for a two-platform deployment:

- Backend: FastAPI on Railway
- Frontend: Next.js on Vercel

## 1. Before deployment

Make sure the project is pushed to GitHub and the repository does not contain real secrets.

Do not commit:

```text
.env
.venv/
__pycache__/
node_modules/
```

Commit these files:

```text
.env.example
frontend/.env.example
frontend/.env.production.example
Dockerfile
railway.json
frontend/vercel.json
```

## 2. Railway backend deployment

Railway should deploy the backend from the repository root.

### Railway settings

Use these values:

```text
Root directory: /
Builder: Dockerfile auto-detect
Start command: uvicorn backend.app.main:app --host 0.0.0.0 --port ${PORT:-8000}
Healthcheck path: /health
```

The repository already includes `railway.json`, so Railway can read the start command and healthcheck path automatically.

### Railway environment variables

Add these variables in Railway → Service → Variables:

```env
OPENAI_API_KEY=your_openai_api_key
OPENAI_MODEL=gpt-4o-mini
DATABASE_URL=sqlite+aiosqlite:///./jobs.db
SCORING_CONCURRENCY=3
PAGE_SIZE=3
BOT_TOKEN=optional_if_you_run_telegram_bot
```

For a stronger production setup, replace SQLite with Railway PostgreSQL and set:

```env
DATABASE_URL=postgresql+asyncpg://USER:PASSWORD@HOST:PORT/DB_NAME
```

### After Railway deploy

Open:

```text
https://your-railway-domain/health
```

Expected response:

```json
{
  "status": "ok",
  "service": "job-ai-agent"
}
```

Also test Swagger:

```text
https://your-railway-domain/docs
```

## 3. Vercel frontend deployment

Deploy the frontend as a separate Vercel project from the same GitHub repository.

### Vercel settings

Use these values:

```text
Framework Preset: Next.js
Root Directory: frontend
Install Command: npm install
Build Command: npm run build
Output Directory: .next
```

### Vercel environment variables

Add this variable in Vercel → Project → Settings → Environment Variables:

```env
NEXT_PUBLIC_API_URL=https://your-railway-domain
```

Important: do not add `/chat` at the end. The frontend code adds `/chat` automatically.

Correct:

```env
NEXT_PUBLIC_API_URL=https://jobfinder-backend-production.up.railway.app
```

Incorrect:

```env
NEXT_PUBLIC_API_URL=https://jobfinder-backend-production.up.railway.app/chat
```

## 4. Local production-like check

Backend:

```powershell
uvicorn backend.app.main:app --host 0.0.0.0 --port 8000
```

Frontend:

```powershell
cd frontend
npm install
$env:NEXT_PUBLIC_API_URL="http://localhost:8000"
npm run build
npm run start
```

Open:

```text
http://localhost:3000
```

## 5. Deployment checklist

- [ ] GitHub repository is public or connected to Railway/Vercel
- [ ] `.env` is not committed
- [ ] Railway backend deploy is successful
- [ ] Railway `/health` works
- [ ] Railway `/docs` works
- [ ] Vercel root directory is `frontend`
- [ ] Vercel `NEXT_PUBLIC_API_URL` points to Railway backend URL
- [ ] Frontend can call backend `/chat`
- [ ] README contains live frontend and backend links

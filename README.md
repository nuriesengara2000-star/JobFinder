# JobFinder AI Agent

JobFinder AI Agent is an autonomous AI job-search assistant that analyzes a user's resume, searches real vacancies from multiple sources, and returns relevant job opportunities with a clean web interface.


## Live Demo

Frontend: https://job-finder-lemon-ten.vercel.app

Backend API: https://jobfinder-production-739b.up.railway.app  

API Docs: https://jobfinder-production-739b.up.railway.app/docs

Demo-Video: https://youtu.be/n-03yVfZeJA

## Screenshots

docs\screenshots

## Project Status

Current version includes:

- ReAct-style autonomous agent
- Resume parsing with OpenAI
- Multi-source job search tools
- Telegram bot interface
- PostgreSQL database models with SQLAlchemy
- FastAPI backend with `GET /health` and `POST /chat`
- Pydantic request validation
- Server-Sent Events streaming response
- Basic request logging
- Basic in-memory rate limiting
- Modern Next.js frontend for resume-based job search
- Dockerfile for backend
- Dockerfile for frontend
- `docker-compose.yml` for local full-stack launch

Planned next steps:

- User authentication
- Persistent search history
- PDF/DOCX resume upload from web UI
- LangSmith observability

## Problem

Junior and middle developers often spend a lot of time searching for relevant jobs across multiple platforms. Many job boards return unrelated vacancies, and candidates still need to manually compare requirements with their resume.

## Solution

This project uses an AI agent to:

1. Parse the user's resume.
2. Identify skills, target role, and experience level.
3. Search real jobs from several job sources.
4. Collect vacancies through custom tools.
5. Return a ranked and readable list of job opportunities.

## Main Features

- **Autonomous ReAct Agent**: the agent uses a Thought → Action → Observation → Final Answer loop.
- **Custom Tools**: resume parser and job search tools for different sources.
- **Real Job Search**: the agent is instructed not to invent vacancies.
- **FastAPI API**: backend endpoints for health check and AI job-search chat.
- **Streaming Response**: `/chat` returns Server-Sent Events for frontend streaming UX.
- **Next.js Frontend**: polished resume input page, workflow block, status messages, and job-result cards.
- **Telegram Bot**: additional working interface for sending resumes and getting vacancies.
- **Database Layer**: SQLAlchemy models for jobs, saved jobs, users, and applications.
- **Dockerized Setup**: backend and frontend can be launched together with Docker Compose.

## Tech Stack

### Backend

- Python
- FastAPI
- Pydantic
- OpenAI API
- SQLAlchemy Async
- PostgreSQL / asyncpg
- Aiogram
- Uvicorn

### Frontend

- Next.js
- React
- TypeScript
- Tailwind CSS
- Server-Sent Events client parser

### AI Agent

- ReAct-style custom agent loop
- OpenAI model: `gpt-4o-mini` by default
- Custom tools for job search and resume parsing

### Deployment

- Backend: Railway
- Frontend: Vercel
- Containerization: Docker

## Project Structure

```text
job_ai_agent/
├── backend/
│   └── app/
│       ├── api/
│       │   ├── chat.py
│       │   └── health.py
│       ├── core/
│       │   ├── logging.py
│       │   └── rate_limit.py
│       ├── schemas/
│       │   └── chat.py
│       └── main.py
├── frontend/
│   ├── app/
│   │   ├── globals.css
│   │   ├── layout.tsx
│   │   └── page.tsx
│   ├── lib/
│   │   └── api.ts
│   ├── Dockerfile
│   ├── package.json
│   ├── tailwind.config.ts
│   └── next.config.mjs
├── bot/
├── db/
├── react_agent/
├── services/
├── alembic/
├── Dockerfile
├── docker-compose.yml
├── .dockerignore
├── requirements.txt
├── .env.example
├── .gitignore
└── README.md
```

## Environment Variables

Create a local `.env` file based on `.env.example`:

```env
BOT_TOKEN=your_telegram_bot_token_here
OPENAI_API_KEY=your_openai_api_key_here
OPENAI_MODEL=gpt-4o-mini
DATABASE_URL=postgresql+asyncpg://user:password@host:5432/database
SCORING_CONCURRENCY=3
PAGE_SIZE=3
```

Important: never commit your real `.env` file to GitHub.

For the frontend, create `frontend/.env.local` if you run it without Docker:

```env
NEXT_PUBLIC_API_URL=http://localhost:8000
```

## Local Setup Without Docker

### 1. Create virtual environment

```bash
python -m venv .venv
```

### 2. Activate virtual environment

Windows PowerShell:

```bash
.venv\Scripts\Activate.ps1
```

macOS / Linux:

```bash
source .venv/bin/activate
```

### 3. Install backend dependencies

```bash
pip install -r requirements.txt
```

### 4. Create `.env`

```bash
cp .env.example .env
```

Then add your real values.

### 5. Run FastAPI backend

```bash
uvicorn backend.app.main:app --reload
```

Backend URL:

```text
http://127.0.0.1:8000
```

Swagger documentation:

```text
http://127.0.0.1:8000/docs
```

### 6. Run frontend

```bash
cd frontend
npm install
npm run dev
```

Frontend URL:

```text
http://localhost:3000
```

## Running With Docker Compose

Create `.env` first:

```bash
cp .env.example .env
```

Then run the full stack:

```bash
docker-compose up --build
```

Available services:

```text
Frontend: http://localhost:3000
Backend:  http://localhost:8000
Swagger:  http://localhost:8000/docs
Health:   http://localhost:8000/health
```

## API Endpoints

### GET `/health`

Checks that the backend is running.

Example response:

```json
{
  "status": "ok",
  "service": "job-ai-agent"
}
```

### POST `/chat`

Runs the AI job-search agent using resume text.

Request body:

```json
{
  "resume_text": "Python developer resume text with skills, projects, and experience..."
}
```

Response type:

```text
text/event-stream
```

The endpoint sends events:

- `status` — agent started
- `final` — final answer with parsed resume and collected jobs
- `error` — error message if something fails

## Running Telegram Bot

```bash
python -m bot.main
```

Make sure `BOT_TOKEN`, `OPENAI_API_KEY`, and `DATABASE_URL` are set in `.env`.

## Railway Backend Deployment Plan

For Railway, deploy the repository root and use the root `Dockerfile`. Required variables:

```env
OPENAI_API_KEY=...
OPENAI_MODEL=gpt-4o-mini
DATABASE_URL=...
BOT_TOKEN=...
```

Start command is already defined in the Dockerfile:

```bash
uvicorn backend.app.main:app --host 0.0.0.0 --port 8000
```

## Vercel Frontend Deployment Plan

For Vercel:

1. Set the project root to `frontend`.
2. Add environment variable:

```env
NEXT_PUBLIC_API_URL=https://your-railway-backend-url
```

3. Deploy with default Next.js settings.

## Known Limitations

- The `/chat` endpoint uses streaming response format, but the current agent returns the final answer after the full ReAct loop. Next version should stream each agent step and token.
- Rate limiting is in-memory. For production with multiple workers, Redis should be used.
- Docker Compose currently expects an existing `.env` file.
- Some job sources may fail if their public pages or APIs change.
- Full frontend chat history is not persisted yet.

## Roadmap

- Add frontend session history persistence.
- Add PDF/DOCX upload directly from the web UI.
- Add observability with LangSmith.
- Add stronger prompt-injection protection.
- Add job fit-score visualization.
- Add PostgreSQL in production instead of SQLite.

## Capstone Requirements Coverage

| Requirement | Current Status |
|---|---|
| Autonomous agent / multi-agent system | Done |
| Minimum one custom tool | Done |
| FastAPI production-ready API | Done |
| Pydantic validation | Added |
| Streaming response | Basic SSE added |
| Logging | Added |
| Rate limiting | Added |
| React / Next.js frontend | Added |
| Dockerfile | Added |
| Docker Compose | Added |
| Tests | Added |
| Proposal | Added: `docs/proposal.md` |
| Architecture diagram | Added: `docs/architecture.png` |
| Demo Day presentation | Added: `docs/JobFinder_Demo_Day_Presentation.pdf` |
| Cloud deployment | Done: Railway backend + Vercel frontend |
| README | Added |
| `.env.example` | Added |

## Deployment: Railway + Vercel

The project is prepared for separate deployment:

- **Backend:** Railway, from the repository root, using `Dockerfile` and `railway.json`.
- **Frontend:** Vercel, from the `frontend` root directory.

### Railway backend

Railway settings:

```text
Root Directory: /
Healthcheck Path: /health
Start Command: uvicorn backend.app.main:app --host 0.0.0.0 --port ${PORT:-8000}
```

Required Railway variables:

```env
OPENAI_API_KEY=your_openai_api_key
OPENAI_MODEL=gpt-4o-mini
DATABASE_URL=sqlite+aiosqlite:///./jobs.db
SCORING_CONCURRENCY=3
PAGE_SIZE=3
```

After deployment, check:

```text
https://your-railway-domain/health
https://your-railway-domain/docs
```

### Vercel frontend

Vercel settings:

```text
Framework Preset: Next.js
Root Directory: frontend
Install Command: npm install
Build Command: npm run build
```

Required Vercel variable:

```env
NEXT_PUBLIC_API_URL=https://your-railway-backend-domain
```

Full deployment guide: `docs/DEPLOYMENT.md`.

## Tests

Run backend tests:

```bash
python -m pytest backend/tests -q
```

Current coverage includes:

- root endpoint;
- health endpoint;
- chat validation;
- job matching filter for irrelevant roles.

## Final Submission Artifacts

- Proposal: `docs/proposal.md`
- Architecture diagram: `docs/architecture.png`
- Presentation PDF: `docs/JobFinder_Demo_Day_Presentation.pdf`
- Presentation PPTX: `docs/JobFinder_Demo_Day_Presentation.pptx`
- Demo video slideshow: `docs/demo.mp4`
- Demo recording script: `docs/demo_video_script.md`
- Demo recording checklist: `docs/demo_recording_checklist.md`

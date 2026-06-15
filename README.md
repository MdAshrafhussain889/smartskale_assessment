# SmartSkale — Assessment Platform

This repository contains two main applications:

- `hiremind_backend` — FastAPI backend (Python, SQLAlchemy, Alembic)
- `hiremind_frontend` — Next.js frontend (TypeScript, Tailwind)

This README explains how to run the project locally, apply database migrations, run the frontend, and push the code to GitHub.

**Important safety note**: The project integrates with AI and a remote code execution service (Judge0). Do not enable any local in-process code execution. Use Judge0 (or an isolated sandbox) for running user-submitted code.

**Table of contents**

- **Project layout**
- **Prerequisites**
- **Backend: setup & run**
- **Database migrations (Alembic)**
- **Frontend: setup & run**
- **Environment variables**
- **Pushing to GitHub**
- **Developer notes & troubleshooting**
- **Contributing**
- **License & contact**

**Project layout**

- `hiremind_backend/` — FastAPI service. Key files:
  - `app/main.py` — app entry
  - `app/core/` — config, database, security
  - `app/api/routes/` — routers (auth, assessments, ai, code, attempts, etc.)
  - `app/models/` — SQLAlchemy models
  - `app/schemas/` — Pydantic request/response models
  - `alembic/` — migration scripts
- `hiremind_frontend/` — Next.js app (App Router)
  - `src/app/` — pages and route components
  - `src/lib/api.ts` — API helpers
  - `src/types/` — shared TypeScript types

Prerequisites

- Git (2.x+)
- Python 3.10+ (use virtualenv/venv)
- Node.js 16+ (or supported LTS for Next.js in the project)
- PostgreSQL (or adjust DATABASE_URL to a running Postgres)
- (Optional) Docker + Docker Compose if you prefer containerized setup

Backend: setup & run (local dev)

1. Create and activate a Python virtual environment

```powershell
cd "C:\Users\Test1\Music\SmartSkale\hiremind_backend"
python -m venv venv
venv\Scripts\Activate.ps1   # PowerShell
# or: venv\Scripts\activate (cmd.exe)
```

2. Install Python dependencies

```powershell
pip install -r requirements.txt
```

3. Set environment variables (example .env)

Create a `.env` file in `hiremind_backend` or export vars in your shell. Minimal required values:

```
DATABASE_URL=postgresql://user:password@localhost:5432/smartskale
JWT_SECRET=replace-with-secure-secret
JUDGE0_URL=https://judge0.example/api
OPENAI_API_KEY=sk-...
```

4. Apply Alembic migrations (see next section)

5. Run the dev server

```powershell
# from hiremind_backend
python -m uvicorn app.main:app --reload --port 8000
```

The API will be available at `http://127.0.0.1:8000`.

Database migrations (Alembic)

1. Configure `DATABASE_URL` in environment
2. Create migrations after model changes:

```powershell
cd hiremind_backend
alembic revision --autogenerate -m "describe change"
alembic upgrade head
```

If you encounter errors about `alembic` version string length (rare on some DBs), ensure Alembic revision identifiers are short.

Frontend: setup & run

1. Change to the frontend directory and install packages

```powershell
cd "C:\Users\Test1\Music\SmartSkale\hiremind_frontend"
npm install
# or: pnpm install / yarn
```

2. Create `.env.local` in `hiremind_frontend` with the API URL

```
NEXT_PUBLIC_API_URL=http://127.0.0.1:8000
```

3. Run the Next dev server

```powershell
npm run dev
# opens at http://localhost:3000
```

Environment variables (recommended)

- `DATABASE_URL` — Postgres connection string
- `JWT_SECRET` — secret for JWTs (keep private)
- `OPENAI_API_KEY` — API key for AI services (if used)
- `JUDGE0_URL` & `JUDGE0_TOKEN` — Judge0 endpoint and token
- Other provider credentials as needed (e.g., SENTRY_DSN)

Pushing the repo to GitHub (single repo)

From the project root (`C:\Users\Test1\Music\SmartSkale`):

```powershell
git init
git add .
git commit -m "Initial commit: backend + frontend + README"
git branch -M main
git remote add origin https://github.com/<YOUR_USERNAME>/smartskale_assessment.git
git push -u origin main
```

If you prefer SSH, replace the `remote add` URL with `git@github.com:...`.

If you want separate repos for frontend and backend, either push each folder separately (initialize separate git repos inside each folder) or use `git subtree split` to push subdirectories while preserving history.

Developer notes & troubleshooting

- If `uvicorn` fails at import time, check for indentation or syntax errors introduced during editing.
- If creating assessments fails with DB errors (UndefinedColumn), run `alembic upgrade head` to sync schema.
- Ensure `JWT_SECRET` is set — the server validates secret strength at startup.
- Do not enable any local in-process code execution; use Judge0.
- AI question generation: if responses don't match requested types, verify the `types` and `counts` you send in the request and confirm backend logs. The backend enforces per-type counts and clamps values.

Testing & CI

- No automatic test suite is included; consider adding `pytest` for backend unit tests and Playwright/Jest for frontend.
- Add a `pre-commit` hook to run linters/formatters (e.g., `black`, `ruff`, `eslint`, `prettier`).

Contributing

- Fork the repo, create feature branches, open PRs against `main`. Describe changes and include migrations if models change.

Security & privacy

- Do not commit secrets (`.env`, `.env.local`, tokens) to the repository. Add them to `.gitignore`.
- Keep dependencies up to date and review third-party packages.

Contact

- For issues or questions, open a GitHub issue in the repo.

License

- Add a `LICENSE` file at the repo root (MIT / Apache-2.0 / whichever you prefer).

---

This README is intended to get a developer up and running quickly. If you want, I can also:

- Add a `Makefile` / `scripts` to standardize dev commands
- Create `docker-compose.yml` examples for local Postgres + Judge0 + app orchestration
- Add a `CONTRIBUTING.md` and `CODE_OF_CONDUCT.md`


# SmartSkale Assessment

SmartSkale Assessment is a full-stack online assessment platform for recruiters and candidates. Recruiters can create AI-generated assessments, publish them, review attempts, run code submissions, monitor proctoring signals, and view AI-based evaluation reports.

## Features

- Recruiter and candidate authentication
- Assessment creation with templates
- AI-generated MCQ, coding, SQL, and aptitude questions
- Candidate attempt flow with timer
- Code execution support through Judge0
- Proctoring options and event tracking
- AI evaluation with score and hiring recommendation
- Recruiter dashboard for recent attempts and reports

## Tech Stack

- Frontend: Next.js, React, TypeScript, Tailwind CSS
- Backend: FastAPI, SQLAlchemy, Alembic
- Database: PostgreSQL
- Cache/Queue: Redis
- AI: OpenAI API
- Code Runner: Judge0

## Project Structure

```text
SmartSkale/
  hiremind_frontend/   Next.js frontend app
  hiremind_backend/    FastAPI backend app
```

## Backend Setup

```bash
cd hiremind_backend
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```

Update `.env` with your database, OpenAI, JWT, and Judge0 settings.

Run migrations:

```bash
alembic upgrade head
```

Start backend:

```bash
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

## Frontend Setup

```bash
cd hiremind_frontend
npm install
npm run dev
```

Frontend runs at:

```text
http://localhost:3000
```

Backend runs at:

```text
http://127.0.0.1:8000
```

## Push To GitHub

Repository URL:

```text
https://github.com/MdAshrafhussain889/smartskale_assessment.git
```

Use these commands from the project root:

```bash
git init
git add .
git commit -m "Initial SmartSkale assessment project"
git branch -M main
git remote add origin https://github.com/MdAshrafhussain889/smartskale_assessment.git
git push -u origin main
```

If `origin` already exists:

```bash
git remote set-url origin https://github.com/MdAshrafhussain889/smartskale_assessment.git
git push -u origin main
```

## Notes

- Do not commit `.env` files.
- Make sure PostgreSQL, Redis, and Judge0 are running before testing backend features.
- Use strong secrets in production.

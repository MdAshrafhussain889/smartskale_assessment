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

# Spoorthi Chatbot

Spoorthi Chatbot is a deployable fest-assistant web app for answering questions about Spoorthi using a local grounded RAG pipeline, an admin-managed knowledge base, and a polished Next.js chat UI.

## Stack

Backend:
- FastAPI
- FAISS-backed in-memory index rebuilt at startup
- JWT admin authentication
- semantic chunking + retrieval + reranking
- local grounded response engine

Frontend:
- Next.js App Router
- Tailwind CSS
- Framer Motion
- dark mode
- quick-question dropdown
- admin console at `/admin`

## Project Layout

```text
backend/
  app/
    api/
    models/
    services/
    utils/
    config.py
    main.py
  requirements.txt
  .env.example
  sample_data/

frontend/
  app/
  components/
  lib/
  package.json
  .env.example

render.yaml
docker-compose.yml
README.md
```

## Local Run

1. Install backend dependencies:

```bash
cd backend
python -m pip install -r requirements.txt
```

2. Install frontend dependencies:

```bash
cd frontend
npm install
```

3. Configure backend env using [backend/.env.example](C:\Users\surya\Desktop\spoorthi_ai\backend\.env.example)

Important values:
- `LOCAL_MODEL_NAME=local-context`
- `LOAD_REPO_KNOWLEDGE=true`
- `PERSIST_RUNTIME_KNOWLEDGE=false`
- `JWT_SECRET`
- `ADMIN_USERNAME`
- `ADMIN_PASSWORD`
- `SPOORTHI_DEV_MODE=true`
- `ALLOWED_ORIGINS=http://localhost:3000`

4. Configure frontend env using [frontend/.env.example](C:\Users\surya\Desktop\spoorthi_ai\frontend\.env.example)

```env
NEXT_PUBLIC_API_URL=http://localhost:8000
```

5. Start the full app:

```bash
python backend/app/main.py
```

Open:
- frontend: `http://localhost:3000`
- backend health: `http://127.0.0.1:8000/health`
- backend docs: `http://127.0.0.1:8000/docs`

## Docker

```bash
docker compose up --build
```

This starts:
- backend on `8000`
- frontend on `3000`
- runtime backend data from `backend/data`

## Deployment

Recommended setup:
- deploy [backend](C:\Users\surya\Desktop\spoorthi_ai\backend) to Render
- deploy [frontend](C:\Users\surya\Desktop\spoorthi_ai\frontend) to Vercel

Free-tier architecture:
- permanent bundled fest knowledge lives in `backend/sample_data`
- the backend rebuilds the FAISS index from those repo files on startup
- admin uploads and manual additions work during the live service session
- runtime admin changes are temporary on Render Free and can be lost after restart or redeploy

### Render backend

Use [render.yaml](C:\Users\surya\Desktop\spoorthi_ai\render.yaml).

Configured:
- root directory: `backend`
- start command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
- health check path: `/health`
- free-tier friendly startup rebuild from `backend/sample_data`

Important backend envs:
- `LOCAL_MODEL_NAME`
- `LOAD_REPO_KNOWLEDGE`
- `PERSIST_RUNTIME_KNOWLEDGE`
- `JWT_SECRET`
- `ADMIN_USERNAME`
- `ADMIN_PASSWORD`
- `ALLOWED_ORIGINS`

### Vercel frontend

Deploy with root directory `frontend`.

Set:

```env
NEXT_PUBLIC_API_URL=https://your-backend.onrender.com
```

Then set backend `ALLOWED_ORIGINS` to your Vercel domain.

## Features

- Spoorthi Chatbot branding across the UI
- admin login and knowledge management
- upload `.pdf`, `.txt`, `.md`
- add manual context instantly
- delete indexed documents
- rebuild the index from the admin panel
- permanent repo-backed knowledge bootstrapping from `backend/sample_data`
- friendly small-talk handling
- direct answers for common fest questions
- grounded fallback:
  `I don't have that information. Please contact the organizers.`
- contact enrichment when valid organizer details exist in the knowledge base

## Quick Test Questions

- `Where is Hackathon?`
- `What are the event timings?`
- `List all events`
- `Where is Robotics Workshop?`
- `How can I contact the organizers?`

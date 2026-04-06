# Spoorthi Chatbot

Spoorthi Chatbot is a fest-assistant project for answering questions about Spoorthi using retrieved document context, curated quick replies, and an admin-managed knowledge base.

The repository currently contains **two runnable app paths**:

1. **Primary app**: `backend/` + `frontend/`
   This is the main product path and the one the recent work has been focused on.
   It uses:
   - FastAPI backend
   - Next.js frontend
   - live document indexing
   - admin console
   - local grounded response engine

2. **Lightweight demo app**: root-level `main.py`
   This is a smaller Flask-based fallback/demo app that serves `templates/` + `static/` directly.

If you want the current full UI with admin, voice input, dark mode, quick questions, and the richer RAG flow, use the **primary app**.

**Current Recommended Run Mode**

Use the combined launcher in [backend/app/main.py](C:\Users\surya\Desktop\spoorthi_ai\backend\app\main.py):

```bash
python backend/app/main.py
```

What it does:
- starts the FastAPI backend on `http://127.0.0.1:8000`
- starts the Next.js frontend on `http://localhost:3000`
- opens the frontend automatically in your browser
- runs in dev mode by default, so code changes show up after refresh

**Primary App Stack**

Backend:
- FastAPI
- FAISS-backed persistent knowledge index
- admin auth with JWT + bcrypt
- retriever + reranker pipeline
- local grounded response engine
- manual context injection and document upload

Frontend:
- Next.js App Router
- Tailwind CSS
- Framer Motion
- dark mode
- voice input
- admin console
- quick-question dropdown

**Current Product Features**

Chat experience:
- Spoorthi Chatbot branding across the UI
- streaming-style replies
- quick prepared questions from a dropdown
- friendly handling for greetings and small talk
- fallback messaging when the answer is not in the knowledge base
- organizer contact enrichment on fallback when valid contact details exist in uploaded context

Knowledge management:
- admin login
- upload `.pdf`, `.txt`, `.md`
- add manual knowledge instantly
- delete indexed documents
- rebuild the index from the admin panel

Answering behavior:
- predefined direct answers for a small set of common demo questions
- RAG for general fest questions
- fallback to:
  `I don't have that information. Please contact the organizers.`
- if organizer contact data exists in KB, the bot appends those details to the fallback

**Project Layout**

Main app:

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

frontend/
  app/
  components/
  lib/
  package.json
  .env.example
```

Lightweight Flask demo:

```text
main.py
services/
templates/
static/
data/
requirements.txt
Procfile
runtime.txt
```

**Local Setup**

1. Backend dependencies:

```bash
cd backend
python -m pip install -r requirements.txt
```

2. Frontend dependencies:

```bash
cd frontend
npm install
```

3. Backend environment:

Use [backend/.env.example](C:\Users\surya\Desktop\spoorthi_ai\backend\.env.example) as the starting point.

Important values:
- `LOCAL_MODEL_NAME=local-context`
- `JWT_SECRET`
- `ADMIN_USERNAME`
- `ADMIN_PASSWORD`
- `SPOORTHI_DEV_MODE=true`
- `ALLOWED_ORIGINS=http://localhost:3000`

4. Frontend environment:

Use [frontend/.env.example](C:\Users\surya\Desktop\spoorthi_ai\frontend\.env.example).

Default:

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

6. Optional Docker quick start:

```bash
docker compose up --build
```

The Docker Compose setup now starts:
- the backend with the local response engine
- the frontend pointed at `http://localhost:8000`
- persistent backend data from `backend/data`

**Lightweight Flask Demo**

If you want the smaller single-process Flask version instead:

```bash
python -m pip install -r requirements.txt
python main.py
```

This serves the root `templates/` and `static/` files on port `5000` by default.

Use this mode only if you specifically want the simplified Flask demo. It is not the main product path anymore.

**Deployment Status**

Current repo deployment files are split by app path:

- [render.yaml](C:\Users\surya\Desktop\spoorthi_ai\render.yaml)
  Targets the **FastAPI backend** inside `backend/`

- [Procfile](C:\Users\surya\Desktop\spoorthi_ai\Procfile)
  Targets the **root Flask demo**

- [requirements.txt](C:\Users\surya\Desktop\spoorthi_ai\requirements.txt)
  Root Flask demo dependencies

- [backend/requirements.txt](C:\Users\surya\Desktop\spoorthi_ai\backend\requirements.txt)
  Main FastAPI backend dependencies

So at the moment:
- deploying the main product requires the `backend/` and `frontend/` paths
- deploying the root Flask app uses the root Procfile/requirements

**Recommended Deployment Path**

For the current main product:
- deploy `backend/` to Render or Railway
- deploy `frontend/` to Vercel or a Node host
- set `NEXT_PUBLIC_API_URL` in the frontend deployment
- set `ALLOWED_ORIGINS` in the backend deployment to the final frontend URL

Helpful backend envs for deployment:
- `LOCAL_MODEL_NAME`
- `JWT_SECRET`
- `ADMIN_USERNAME`
- `ADMIN_PASSWORD`
- `ALLOWED_ORIGINS`

**Notes About Current Behavior**

- The chat UI no longer shows confidence badges or document/internet source pills.
- The Next.js dev overlay has been disabled in config, but the primary app still runs in dev mode by default so edits reflect after refresh.
- Live Server / “Go Live” is not the recommended way to use the primary app. Use `python backend/app/main.py` instead.
- A smaller Flask demo still exists at the repo root, which is why the repository has both root-level and `backend/`/`frontend/` startup files.

**Quick Test Questions**

You can try:
- `Where is Hackathon?`
- `What are the event timings?`
- `List all events`
- `Where is Robotics Workshop?`
- `How can I contact the organizers?`

**Known Caveat**

This repository has evolved in-place and now contains both:
- a modern FastAPI + Next.js app
- a simpler Flask demo app

The README now reflects that honestly so startup and deployment are less confusing.

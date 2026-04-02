# Spoorthi_AI

Spoorthi_AI is a deployable hybrid RAG fest assistant with a FastAPI backend and Next.js frontend. It supports provider-based LLM switching (`local`, `openai`, `ollama`), FAISS-backed document retrieval, internet fallback, JWT-protected admin operations, and a premium chat/admin UI.

## Stack

- Backend: FastAPI, FAISS, bcrypt, JWT, DuckDuckGo/SerpAPI fallback, provider-agnostic LLM service
- Frontend: Next.js App Router, Tailwind CSS, Framer Motion
- Deployment: Render/Railway-ready backend, Vercel-ready frontend, Docker support

## Backend Features

- `LLMService` abstraction with OpenAI, Ollama, and a built-in local provider that needs no API key
- Persistent FAISS vector index with incremental chunk appends
- Real-time knowledge injection for uploads and manual context
- Hybrid RAG routing: document first, internet fallback below similarity threshold
- Admin authentication with bcrypt password checks and JWT route protection
- Streaming chat endpoint with document/internet status events

## Frontend Features

- Responsive chat interface with streaming output
- Source badges for `document` and `internet`
- Voice input via Web Speech API
- Dark mode toggle
- Chat history persistence in local storage
- Admin dashboard with drag-and-drop uploads, progress bar, manual context injection, document deletion, and reindex trigger

## Local Setup

### Backend

```bash
cd backend
python -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload
```

### Frontend

```bash
cd frontend
npm install
cp .env.example .env.local
npm run dev
```

## Environment

Key backend variables:

- `LLM_PROVIDER=local|openai|ollama`
- `OPENAI_API_KEY`
- `OLLAMA_BASE_URL`
- `OPENAI_MODEL`, `OLLAMA_MODEL`
- `LLM_TEMPERATURE`
- `LLM_MAX_TOKENS`
- `SIMILARITY_THRESHOLD`
- `JWT_SECRET`
- `ADMIN_USERNAME`
- `ADMIN_PASSWORD` or `ADMIN_PASSWORD_HASH`

Frontend variable:

- `NEXT_PUBLIC_API_URL=http://localhost:8000`

## API

- `POST /ask`
- `POST /ask/stream`
- `POST /admin/login`
- `GET /admin/docs`
- `POST /admin/upload`
- `POST /admin/add-context`
- `DELETE /admin/delete/{id}`
- `POST /admin/reindex`

## Notes

- The backend uses a deterministic hashing embedder and can now answer in `local` mode without any API key.
- For production, replace defaults in `.env` with secure secrets and real admin credentials.

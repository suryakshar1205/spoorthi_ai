# Spoorthi Chatbot
### A grounded full-stack festival assistant for Spoorthi 2026, built to answer event questions with live-manageable knowledge.

![Python](https://img.shields.io/badge/Python-3.11+-3776AB?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-Backend-009688?logo=fastapi&logoColor=white)
![Next.js](https://img.shields.io/badge/Next.js-15-000000?logo=nextdotjs&logoColor=white)
![React](https://img.shields.io/badge/React-19-61DAFB?logo=react&logoColor=black)
![TypeScript](https://img.shields.io/badge/TypeScript-Frontend-3178C6?logo=typescript&logoColor=white)
![FAISS](https://img.shields.io/badge/FAISS-Vector%20Search-5C2D91)
![Status](https://img.shields.io/badge/Status-Active-2EA043)

## 🚀 Overview
Spoorthi Chatbot is a domain-specific question answering system for the Spoorthi technical fest at JNTUH. It combines a polished Next.js chat experience with a FastAPI backend, a local retrieval pipeline, and an admin console for managing event knowledge without changing code.

Why it matters:
- Fest information is often scattered across posters, PDFs, coordinators, and informal updates.
- Students need fast answers about events, venues, timings, coordinators, workshops, and day-wise schedules.
- Organizers need a practical way to update the assistant as details evolve.

This project solves that by grounding responses in curated knowledge files and admin-added context, while still keeping the product deployable, lightweight, and easy to operate.

## ✨ Key Features
- **Grounded fest Q&A** powered by bundled Spoorthi knowledge, semantic retrieval, reranking, and local response generation.
- **Streaming chat responses** with Server-Sent Events for a smoother real-time user experience.
- **Curated quick-question categories** for common fest queries like events, coordinators, workshops, sponsors, and impact.
- **Voice input support** in the chat UI using browser speech recognition.
- **Admin knowledge console** with login, document upload, manual context injection, delete, and reindex workflows.
- **Upload support for `.pdf`, `.txt`, and `.md`** so organizers can expand the knowledge base without code edits.
- **Predefined answer routing** for high-frequency fest questions that need exact, stable responses.
- **Event-aware responses** for day-wise schedules, locations, timings, coordinators, and role lookups.
- **Typo-tolerant query handling** through spelling correction, normalization, and fuzzy matching.
- **Local-first architecture** with no mandatory external LLM dependency in the default configuration.

## 🛠️ Tech Stack
### Frontend
- **Next.js 15**
- **React 19**
- **TypeScript**
- **Tailwind CSS**
- **Framer Motion**
- **Lucide React**

### Backend
- **FastAPI**
- **Python 3.11**
- **FAISS** for vector search
- **Custom local embedding + retrieval pipeline**
- **JWT authentication** for admin access

### Tools / Libraries
- **PyPDF** for document text extraction
- **DuckDuckGo Search / SerpAPI hooks** for optional web fallback
- **bcrypt** and **python-jose** for authentication
- **pytest** and **pytest-asyncio** for backend testing
- **Docker** and **Docker Compose** for containerized runs
- **Render + Vercel friendly deployment setup**

## 📂 Project Structure
```text
spoorthi_ai/
├── backend/
│   ├── app/
│   │   ├── api/            # User and admin API routes
│   │   ├── models/         # Request/response and domain models
│   │   ├── services/       # RAG, auth, vector search, memory, retrieval logic
│   │   ├── utils/          # Text processing and document helpers
│   │   ├── config.py       # Environment-driven settings
│   │   └── main.py         # FastAPI app bootstrap + local full-stack launcher
│   ├── sample_data/        # Bundled Spoorthi knowledge files
│   ├── tests/              # Backend test suite
│   ├── requirements.txt
│   ├── .env.example
│   └── Dockerfile
├── frontend/
│   ├── app/                # Next.js app router pages
│   ├── components/         # Chat UI, admin UI, toasts, theme controls
│   ├── lib/                # API client, storage helpers, shared types
│   ├── package.json
│   └── Dockerfile
├── logs/                   # Local frontend runtime logs
├── docker-compose.yml
├── render.yaml
└── README.md
```

## ⚙️ Installation & Setup
### Prerequisites
- **Python 3.11+**
- **Node.js 18+** and **npm**
- Optional: **Docker Desktop** if you want to run containers

### 1. Clone the repository
```bash
git clone <your-repo-url>
cd spoorthi_ai
```

### 2. Set up the backend
```bash
cd backend
python -m venv .venv
```

Activate the virtual environment:

**Windows (PowerShell)**
```powershell
.venv\Scripts\Activate.ps1
```

**macOS / Linux**
```bash
source .venv/bin/activate
```

Install dependencies:
```bash
pip install -r requirements.txt
```

Create your backend environment file from the example:

**Windows (PowerShell)**
```powershell
Copy-Item .env.example .env
```

**macOS / Linux**
```bash
cp .env.example .env
```

Important backend variables:
- `SPOORTHI_DEV_MODE=true`
- `LOCAL_MODEL_NAME=local-context`
- `LOAD_REPO_KNOWLEDGE=true`
- `PERSIST_RUNTIME_KNOWLEDGE=false`
- `ALLOWED_ORIGINS=http://localhost:3000`
- `JWT_SECRET=change-me-in-production`
- `ADMIN_USERNAME=admin`
- `ADMIN_PASSWORD=admin123`

### 3. Set up the frontend
Open a new terminal:

```bash
cd frontend
npm install
```

Create `frontend/.env.local` and add:
```env
NEXT_PUBLIC_API_URL=http://127.0.0.1:8000
```

### 4. Optional: run with Docker
From the project root:
```bash
docker compose up --build
```

This starts:
- Frontend on `http://localhost:3000`
- Backend on `http://127.0.0.1:8000`

## ▶️ Usage
### Recommended local development flow
Run the backend in one terminal:
```bash
cd backend
uvicorn app.main:app --reload
```

Run the frontend in another terminal:
```bash
cd frontend
npm run dev
```

Open:
- **Chat UI:** `http://localhost:3000`
- **Admin Console:** `http://localhost:3000/admin`
- **Backend Health:** `http://127.0.0.1:8000/health`
- **API Docs:** `http://127.0.0.1:8000/docs`

### One-command local startup
If you want the project to launch the frontend automatically from the backend entrypoint:
```bash
python backend/app/main.py
```

This mode attempts to:
- start the FastAPI backend
- install frontend dependencies if missing
- launch the Next.js frontend
- write frontend logs to `logs/frontend.out.log` and `logs/frontend.err.log`

### Example workflows
#### Chat experience
- Ask about event locations, timings, coordinators, schedules, sponsors, and workshops.
- Use the quick-question panel for common fest FAQs.
- Speak queries directly using the microphone button when browser support is available.

#### Admin experience
1. Open `/admin`
2. Log in with `ADMIN_USERNAME` and `ADMIN_PASSWORD`
3. Upload `.pdf`, `.txt`, or `.md` files
4. Add manual context instantly
5. Delete outdated documents or rebuild the knowledge base

### Quality checks
Run backend tests:
```bash
python -m pytest backend/tests -q
```

Run frontend checks:
```bash
cd frontend
npm run lint
npm run typecheck
```

## 📸 Screenshots / Demo
Screenshots are not bundled in the repository yet. Good additions for this section would be:
- Chat homepage
- Quick-question panel
- Streaming answer state
- Admin knowledge console
- Upload and reindex workflow

Suggested asset paths:
- `docs/screenshots/chat-ui.png`
- `docs/screenshots/admin-console.png`
- `docs/screenshots/quick-questions.png`

## 💡 Unique Selling Points
- **Not just a chatbot UI:** this project includes the operational tooling needed to keep answers fresh during a live event.
- **Grounded, domain-specific retrieval:** answers are based on actual Spoorthi knowledge instead of generic open-ended generation.
- **Admin-manageable knowledge base:** organizers can upload files and inject context without redeploying frontend code.
- **Local-first by design:** the default setup avoids dependence on paid external LLM infrastructure.
- **Strong portfolio value:** it demonstrates frontend UX, backend APIs, retrieval systems, authentication, testing, and deployment readiness in one project.

## 🚧 Future Improvements
- Persistent knowledge storage across restarts and redeploys
- Richer admin roles and audit trails
- Analytics for unanswered questions and FAQ gaps
- Better document ingestion for schedules, posters, and tabular data
- Multilingual support for festival audiences
- More polished demo assets and contributor documentation

## 🤝 Contributing
Contributions are welcome, especially around retrieval quality, UI polish, documentation, and deployment improvements.

Basic contribution flow:
1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run the backend tests and frontend checks
5. Open a pull request with a clear summary

When contributing, please keep changes grounded in the actual project scope and avoid introducing undocumented assumptions into the fest knowledge layer.

## 📄 License
This repository currently does **not** include a `LICENSE` file.

If you plan to distribute, reuse, or open-source the project publicly, add an explicit license first so contributors and users know the terms clearly.

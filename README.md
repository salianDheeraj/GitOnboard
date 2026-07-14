# Repository Intelligence Platform

Repository Intelligence Platform is a FastAPI + React MVP for importing GitHub repositories and exploring their structure, dependencies, call relationships, semantic search, and generated summaries.

## Current Progress

- FastAPI backend is wired up with repository import, listing, deletion, scan, parse, dependency graph, and call graph endpoints.
- React frontend has the main dashboard, import flow, and repository detail views.
- Repository detail view exposes file explorer, dependency graph, architecture, call graph, search, semantic search, symbols, and summary tabs.
- Repository metadata, task status, and analysis artifacts are now stored in **PostgreSQL**.
- Imported source code is cloned into `data/repos/`.
- Background tasks (like indexing and LLM summaries) are managed via an in-memory queue, and real-time updates are pushed to the frontend using **Server-Sent Events (SSE)**.
- Local Ollama-backed summary generation is connected through `backend/llm_service.py` to provide deterministic, context-rich summaries.

## Tech Stack

- Python 3.10+
- FastAPI (with SSE for real-time updates)
- PostgreSQL & SQLAlchemy
- ChromaDB
- React 19
- Vite
- React Router
- Tailwind CSS

## Project Structure

- `backend/`: FastAPI app, database models, background task queue, config, logging, and LLM integration.
- `frontend/`: React UI for browsing repositories and generated analysis.
- `data/`: Extracted repositories.
- `docs/`: Supporting documentation, including the architecture snapshot.

## Run Locally

The backend and database are fully containerized using Docker Compose.

**Backend & Database:**

```bash
docker compose up --build -d
```

**Frontend:**

```bash
cd frontend
npm install
npm run dev
```

## Documentation

- [Project Setup](setup.md)
- [Architecture and Progress](architecture.md)

## Contributing

If you plan to contribute to this repository, please review [CONTRIBUTING.md](CONTRIBUTING.md) for details on setting up Git hooks to prevent stale pull requests. You should also configure Git to rebase on pull:

```bash
git config pull.rebase true
```

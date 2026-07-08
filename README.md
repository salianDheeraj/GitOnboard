# Repository Intelligence Platform

Repository Intelligence Platform is a FastAPI + React MVP for importing GitHub repositories and exploring their structure, dependencies, call relationships, semantic search, and generated summaries.

## Current Progress

- FastAPI backend is wired up with repository import, listing, deletion, scan, parse, dependency graph, and call graph endpoints.
- React frontend has the main dashboard, import flow, and repository detail views.
- Repository detail view already exposes file explorer, dependency graph, architecture, call graph, search, semantic search, symbols, and summary tabs.
- Repository metadata is stored locally in `data/repos_metadata.json`, and imported source code is cloned into `data/repos/`.
- Local Ollama-backed summary generation is connected through `backend/llm_service.py`.

## Tech Stack

- Python 3.10+
- FastAPI
- Pydantic Settings
- ChromaDB
- React 19
- Vite
- React Router
- Tailwind CSS

## Project Structure

- `backend/`: FastAPI app, config, logging, and LLM integration.
- `frontend/`: React UI for browsing repositories and generated analysis.
- `data/`: imported repositories and persisted metadata.
- `docs/`: supporting documentation, including the architecture snapshot.

## Run Locally

Backend:

```bash
cd F:\GitOnboard
uv run uvicorn backend.main:app --reload
```

Frontend:

```bash
cd F:\GitOnboard\frontend
npm install
npm run dev
```

## Documentation

- [Project Setup](setup.md)
- [Architecture and Progress](architecture.md)

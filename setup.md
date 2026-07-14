# Project Setup

This guide explains how to set up Repository Intelligence Platform locally, start the backend and frontend, and connect the app to Ollama.

## What You Need

- Node.js 18 or newer
- npm
- Docker and Docker Compose
- Ollama installed and running locally

## Repository Layout

- `backend/` contains the FastAPI application and backend workers.
- `frontend/` contains the React user interface.
- `data/` stores imported repositories.

## Backend and Database Setup

The backend and its PostgreSQL database are fully containerized and managed with Docker Compose.

```bash
docker compose up --build -d
```

The API starts on `http://127.0.0.1:8000` by default. Docker Compose also spins up a PostgreSQL container (port 5432) which the backend connects to for tracking repositories, tasks, and artifacts.

## Frontend Setup

```bash
cd frontend
npm install
npm run dev
```

The frontend starts on the Vite dev server, usually `http://localhost:5173`.

## Ollama Setup

The backend currently uses:

- Base URL: `http://localhost:11434`
- Model: `qwen2.5-coder:7b` (or adjust in `backend/llm_service.py` / `.env`)

To prepare Ollama:

```bash
ollama serve
ollama pull qwen2.5-coder:7b
```

If you are using the Windows Ollama install from WSL, the existing setup may call it through the `ollama.exe` alias. The important part is that Ollama must be reachable at `http://localhost:11434` when the backend sends summary requests.

## How The App Connects

1. Start Ollama first so the LLM endpoint is available.
2. Start the backend services (`docker compose up -d`).
3. Start the React frontend.
4. Open the frontend in the browser and import a GitHub repository.
5. When a repository summary is requested, the backend sends metadata to Ollama at `http://localhost:11434/api/generate`. Real-time progress is streamed back to the frontend using Server-Sent Events (SSE).

## Quick Verification

You can confirm the API is up with:

```bash
curl http://127.0.0.1:8000/
```

You can confirm Ollama is reachable with:

```bash
curl http://localhost:11434/api/tags
```

## Notes

- The project loads configurations from `.env` (check `.env.example`).
- Repository metadata, status tracking, and generated artifacts are stored in a PostgreSQL database container.
- Imported repositories are cloned into the local `data/repos/` volume.
- If you plan to contribute, configure Git to rebase on pull: `git config pull.rebase true`
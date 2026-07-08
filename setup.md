# Project Setup

This guide explains how to set up Repository Intelligence Platform locally, start the backend and frontend, and connect the app to Ollama.

## What You Need

- Python 3.10 or newer
- Node.js 18 or newer
- npm
- Ollama installed and running locally

## Repository Layout

- `backend/` contains the FastAPI application.
- `frontend/` contains the React user interface.
- `data/` stores imported repositories and metadata.

## Backend Setup

The backend is managed with `uv`.

```bash
cd F:\GitOnboard
uv sync
uv run uvicorn backend.main:app --reload
```

The API starts on `http://127.0.0.1:8000` by default.

Run the backend from the repository root so Python can resolve the local `backend` package. If your terminal is already inside `frontend/`, run `Set-Location ..` first.

## Frontend Setup

```bash
cd F:\GitOnboard\frontend
npm install
npm run dev
```

The frontend starts on the Vite dev server, usually `http://localhost:5173`.

## Ollama Setup

The backend currently uses:

- Base URL: `http://localhost:11434`
- Model: `gemma4`

That logic lives in `backend/llm_service.py`.

To prepare Ollama:

```bash
ollama serve
ollama pull gemma4
```

If you are using the Windows Ollama install from WSL, the existing setup may call it through the `ollama.exe` alias. The important part is that Ollama must be reachable at `http://localhost:11434` when the backend sends summary requests.

## How The App Connects

1. Start Ollama first so the LLM endpoint is available.
2. Start the FastAPI backend.
3. Start the React frontend.
4. Open the frontend in the browser and import a GitHub repository.
5. When a repository summary is requested, the backend sends metadata to Ollama at `http://localhost:11434/api/generate`.

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

- The project does not currently require a populated `.env` file.
- Repository metadata is stored locally in `data/repos_metadata.json`.
- Imported repositories are cloned into `data/repos/`.
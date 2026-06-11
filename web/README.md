# Somali-NLP-RESEARCH Web Interface

This folder contains a FastAPI backend and a React + Vite frontend that provide a web interface for the existing Somali-NLP-RESEARCH models.

Overview

- Backend: `web/backend` (FastAPI) — exposes authentication, predict, datasets, and experiments endpoints
- Frontend: `web/frontend` (React + TypeScript + Vite) — minimal admin dashboard and prediction UI

Important

- Do NOT modify repository root files. All new code lives inside `web/`.
- This project does not use Docker.

Quick start (backend)

Important note: Use Python 3.11 (or 3.10) for the backend virtual environment. Python 3.13 may require building Rust-based wheels (pydantic-core) and can fail during pip install.

1. Create a Python 3.11 virtualenv and activate it.
2. Install backend requirements:

```powershell
cd web/backend
# create venv (example using py launcher)
py -3.11 -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

3. Set environment variables (example):

```bash
export MONGODB_URI="mongodb://localhost:27017"
export MONGO_DB_NAME="somali_nlp"
export SECRET_KEY="change-me"
```

4. Run the API:

```bash
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

Quick start (frontend)

```bash
cd web/frontend
npm install
npm run dev
```

Notes

- The backend loads trained model artifacts found in the repository `models/` directory for inference only.
- Use the API endpoints described in the project README.

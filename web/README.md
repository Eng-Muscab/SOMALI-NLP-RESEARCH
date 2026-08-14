# Somali-NLP-RESEARCH Web Interface

This folder contains a FastAPI backend and a React + Vite frontend for the Somali-NLP-RESEARCH models.

## Overview

- Backend: `web/backend` (FastAPI) exposes authentication, prediction, datasets, experiments, metrics, and model endpoints.
- Frontend: `web/frontend` (React + TypeScript + Vite) provides the dashboard and prediction UI.

## One-command local start

```powershell
cd web
.\run_all.ps1
```

This starts:

- Backend docs: `http://127.0.0.1:8000/docs`
- Frontend UI: `http://localhost:5173`

## Backend

Use Python 3.11 or 3.10 for the backend virtual environment.

```powershell
cd web\backend
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

cd ..
.\backend\.venv\Scripts\python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload
```

## Frontend

```powershell
cd web\frontend
npm install
npm.cmd run dev
```

The frontend calls `/api/*` and Vite proxies those requests to `http://localhost:8000`. For a custom API URL, set `VITE_API_BASE_URL` before starting the frontend.

## Database

MongoDB is used for users, auth, dataset metadata, and prediction history. Prediction still works when MongoDB is offline, but history will not be saved. Start MongoDB locally at `mongodb://localhost:27017` for the full app.

By default the API loads the fast, reliable `.joblib` scikit-learn models. Set `LOAD_DEEP_MODELS=true` in `web/backend/.env` if you also want to load Keras or transformer artifacts during startup.

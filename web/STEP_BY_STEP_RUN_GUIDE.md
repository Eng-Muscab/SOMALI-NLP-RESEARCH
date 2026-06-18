# Step-by-Step Run Guide

This guide explains how to run the Somali NLP web project locally:
- Backend: FastAPI
- Frontend: React + Vite
- Database: MongoDB

## 1) Prerequisites

Install these first:

1. Python 3.11 or 3.10
2. Node.js 18+ and npm
3. MongoDB running locally on:
   - mongodb://localhost:27017

If MongoDB is not installed, install it and start the service before running the app.

---

## 2) Open the project folder

```powershell
cd C:\Users\HP\Desktop\final-year\SOMALI-NLP-RESEARCH\web
```

---

## 3) Start the backend

### Option A — Manual start

```powershell
cd C:\Users\HP\Desktop\final-year\SOMALI-NLP-RESEARCH\web\backend
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
cd ..
.\backend\.venv\Scripts\python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8001 --reload
```

### Option B — One-command start

```powershell
cd C:\Users\HP\Desktop\final-year\SOMALI-NLP-RESEARCH\web
.\run_all.ps1
```

Expected backend URL:
- http://127.0.0.1:8001/docs

---

## 4) Start the frontend

Open a new terminal:

```powershell
cd C:\Users\HP\Desktop\final-year\SOMALI-NLP-RESEARCH\web\frontend
npm install
npm run dev
```

Expected frontend URL:
- http://localhost:5173/

---

## 5) Log in

The login issue has been fixed. The backend now creates a built-in demo account automatically when it starts.

Use these credentials:

- Email: demo@somalinlp.io
- Password: Demo12345!

You can also register a new user from the Sign Up page if needed.

---

## 6) Verify everything works

### Backend health

Open:
- http://127.0.0.1:8001/docs

### Frontend

Open:
- http://localhost:5173/

If the page opens and login succeeds, the project is running correctly.

---

## 7) Troubleshooting

### Backend fails to start

- Make sure MongoDB is running.
- Make sure you are in the web folder when starting the backend.
- Reinstall requirements if needed:

```powershell
cd C:\Users\HP\Desktop\final-year\SOMALI-NLP-RESEARCH\web\backend
python -m pip install -r requirements.txt
```

### Frontend fails to start

- Run:

```powershell
cd C:\Users\HP\Desktop\final-year\SOMALI-NLP-RESEARCH\web\frontend
npm install
```

- If port 5173 is busy, stop the other process or change the Vite port.

### Login still fails

- Make sure the backend is running on port 8001.
- Make sure MongoDB is reachable at mongodb://localhost:27017.
- Restart the backend once after MongoDB starts.

---

## 8) Summary

1. Start MongoDB
2. Start backend on port 8001
3. Start frontend on port 5173
4. Open http://localhost:5173/
5. Sign in with:
   - demo@somalinlp.io
   - Demo12345!

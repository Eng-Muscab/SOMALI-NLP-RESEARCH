# 🚀 Running the Web Platform

## Quick Start

### Terminal 1: Backend

```powershell
cd D:\SOMALI-NLP-RESEARCH\web
python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
```

**Expected Output:**

```
INFO:     Uvicorn running on http://0.0.0.0:8000
INFO:     Application startup complete
```

### Terminal 2: Frontend

```powershell
cd D:\SOMALI-NLP-RESEARCH\web\frontend
npm run dev
```

**Expected Output:**

```
VITE v4.4.9  ready in XXX ms
➜  Local:   http://localhost:5174/
```

## Access the Application

- **Frontend**: [http://localhost:5174/](http://localhost:5174/)
- **Backend API**: [http://localhost:8000/](http://localhost:8000/)
- **API Docs**: [http://localhost:8000/docs](http://localhost:8000/docs)

## Login Credentials (for testing)

Use any email/password combination to test authentication.

## Features by Page

### 🏠 Dashboard

- View performance metrics
- See model leaderboard
- Check recent activity
- Monitor accuracy trends

### 🧠 Predict

- Enter Somali text (up to 5000 characters)
- Get AI vs Human classification
- See confidence scores
- Export results

### 🚀 Models

- View all available models
- Compare performance metrics
- See model details
- Use recommended models

### 📊 Experiments

- Browse all experiments
- Compare accuracy across experiments
- View F1 score trends
- Export experiment data

### 📤 Datasets

- Upload CSV/Excel files
- Drag & drop interface
- View dataset statistics
- Manage uploaded files

### 🌙 Theme Toggle

- Located in sidebar footer
- Persistent across sessions
- Light and Dark modes

## Architecture

```
Web Platform
├── Backend (FastAPI)
│   ├── Authentication
│   ├── Prediction API
│   ├── Dataset Management
│   └── MongoDB Integration
│
└── Frontend (React + Vite)
    ├── Dashboard
    ├── Prediction Interface
    ├── Model Management
    ├── Experiments
    ├── Dataset Upload
    └── Authentication
```

## Environment

### Backend Requirements

- Python 3.13
- FastAPI 0.100.0
- Motor 3.7.1 (MongoDB async driver)
- PyMongo 4.17.0

### Frontend Requirements

- Node.js 16+
- npm or yarn
- React 18
- TypeScript 5

## Database

MongoDB is accessed at `mongodb://localhost:27017`

**Ensure MongoDB is running before starting the backend.**

## Build for Production

```bash
cd D:\SOMALI-NLP-RESEARCH\web\frontend
npm run build
```

Production files will be in `dist/` directory.

## Troubleshooting

### Frontend won't start

- Check if port 5173/5174 is in use: `netstat -ano | findstr :5173`
- Clear node_modules: `rm -r node_modules && npm install`
- Clear npm cache: `npm cache clean --force`

### Backend won't start

- Ensure MongoDB is running: `mongod`
- Check if port 8000 is in use: `netstat -ano | findstr :8000`
- Verify Python environment: `python --version`

### API calls fail

- Check backend is running on port 8000
- Verify MongoDB is connected
- Check browser console for CORS errors

## Performance Notes

- Frontend dev server with HMR for fast development
- Backend auto-reload with `--reload` flag
- API responses are mocked if backend is unavailable (graceful fallback)

## Next Steps

1. Customize colors in `tailwind.config.js`
2. Add more chart types in dashboard
3. Implement advanced filtering
4. Add user profile management
5. Set up CI/CD pipeline

---

**For detailed component documentation, see FRONTEND_DESIGN.md**

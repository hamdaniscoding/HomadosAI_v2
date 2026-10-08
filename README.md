# HOMADOS AI · VoiceGuardAI

Real-time AI-generated voice detection over WebSocket audio streams.

## Current status

**Research Preview:** The model is still being trained and its scores have not been validated for production use.
The backend provides:

- A WebSocket endpoint that receives live PCM audio and scores each 5-second window once per second.
- Automatic speaker separation to track multiple speakers on a call independently.
- HTTP endpoints for session history (`GET /api/v1/sessions`).
- All audio is analyzed in memory and is never written to disk. Session scores and metadata are stored only if requested.

## Architecture

```
backend/app/
├── main.py                 FastAPI app factory, CORS, static SPA serving
├── config.py               pydantic-settings configuration
├── schemas.py              Pydantic models for HTTP and WebSocket messages
├── api/
│   ├── http.py             GET /healthz, /api/v1/health, GET /sessions, DELETE /sessions
│   └── ws.py               WebSocket /api/v1/ws
├── core/
│   ├── audio.py            Audio decoding and PCM conversion
│   └── buffer.py           Thread-safe rolling audio buffer
└── session/
    └── stream_session.py   WebSocket session state

frontend/src/
├── App.tsx                 Main React component and Router
├── components/             TopBar, BackgroundField UI pieces
├── lib/
│   └── stream.ts           AudioWorklet capture and WebSocket client state machine
├── pages/                  Home, History, HowItWorks, About
└── styles/                 Global CSS, variables
```

## Setup & Development

### Environment Variables
For backend, set `TORCH_DEVICE=cpu` to force CPU inference (recommended for development without CUDA).

### Backend
```bash
python -m venv .venv
.venv\Scripts\activate    # Windows
pip install -r backend/requirements.txt
pip install -r backend/requirements-ml.txt

# Run backend
TORCH_DEVICE=cpu uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000
```
API docs at `http://127.0.0.1:8000/docs`.

### Frontend
Requires Node 20.
```bash
cd frontend
npm ci
npm run dev
```

Alternatively, use the PowerShell script to run both in development:
```powershell
.\scripts\run_dev.ps1 -Device cpu
```

### Production Build
```bash
cd frontend
npm ci
npm run build
cd ..
uvicorn app.main:app --app-dir backend --host 0.0.0.0 --port 8000
```
FastAPI automatically serves the built frontend (`frontend/dist`) at `/`. The `Dockerfile` and `render.yaml` are also configured for deployment.

## Test

**Backend tests:**
```bash
pytest backend
```

**Frontend tests:**
```bash
cd frontend
npm run test
npx playwright test
```

## API

| Method | Path | Purpose |
|--------|------|--------|
| GET | `/healthz` | Lightweight health check |
| GET | `/api/v1/health` | Detailed system status |
| GET | `/api/v1/sessions` | Fetch session history |
| GET | `/api/v1/sessions/{id}` | Fetch specific session scores |
| DELETE | `/api/v1/sessions/{id}` | Delete a session |
| WS | `/api/v1/ws` | Real-time audio streaming |

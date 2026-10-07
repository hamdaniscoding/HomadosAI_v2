# HOMADOS AI · VoiceGuardAI

Real-time AI-generated voice detection over WebSocket audio streams.

## Current status

**Detector not yet trained or loaded.** The backend provides:

- A WebSocket endpoint that receives live PCM audio and scores each 5-second
  window once per second using a pluggable detector interface.
- An HTTP endpoint for file-based analysis.
- ECAPA-TDNN speaker embedding via SpeechBrain (optional, requires PyTorch).

Until a trained detector is registered, all results return
`{"verdict": null, "reason": "no_detector_loaded"}`.

## Architecture

```
backend/app/
├── main.py                 FastAPI app factory, CORS, static SPA serving
├── config.py               pydantic-settings configuration
├── schemas.py              Pydantic models for HTTP and WebSocket messages
├── features.py             Raw librosa feature extraction
├── api/
│   ├── http.py             GET /healthz, /api/v1/health, POST /analyze, /enroll
│   └── ws.py               WebSocket /api/v1/ws/stream
├── core/
│   ├── audio.py            Audio decoding and PCM conversion
│   └── buffer.py           Thread-safe rolling audio buffer
├── detectors/
│   ├── base.py             Detector protocol interface
│   └── registry.py         Register, list, and retrieve detectors
├── speaker/
│   └── ecapa.py            ECAPA-TDNN encoder with lazy loading
└── session/
    └── stream_session.py   WebSocket session state
```

## WebSocket protocol

Endpoint: `ws://host:port/api/v1/ws/stream`

1. Client sends `{"type":"start","sample_rate":16000,"channels":1,"encoding":"pcm_s16le","mode":"single"}`
2. Server replies `{"type":"ready","session_id":"...","window_seconds":5.0,"hop_seconds":1.0,"detector":null}`
3. Client sends binary frames of raw signed 16-bit little-endian PCM
4. Server sends `{"type":"status",...,"speech_seconds":...}` every 0.5 s and `{"type":"result",...,"speech_ratio":...}` every 1 s (once 5 s of audio exist)
5. Client sends `{"type":"stop"}` to end

## Install

```bash
python -m venv .venv
.venv/Scripts/activate    # Windows
pip install -r backend/requirements.txt

# Optional: for ECAPA speaker embeddings
pip install -r backend/requirements-ml.txt
python scripts/download_pretrained.py --ecapa
```

## Run

```bash
uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000
```

API docs at `http://127.0.0.1:8000/docs`.

## Test

```bash
pip install -r backend/requirements-dev.txt
cd backend
pytest -q
```

## API

| Method | Path | Purpose |
|--------|------|--------|
| GET | `/healthz` | Lightweight health check |
| GET | `/api/v1/health` | Detailed system status |
| POST | `/api/v1/analyze` | Upload audio file for analysis |
| POST | `/api/v1/enroll` | Get ECAPA speaker embedding |
| WS | `/api/v1/ws/stream` | Real-time audio streaming |

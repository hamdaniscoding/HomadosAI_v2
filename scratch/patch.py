import re

with open('docs/API.md', 'r') as f:
    content = f.read()

replacement = '''### POST `/api/v1/analyze`
Upload an audio file for sequential full-file analysis (no skipped hops).

**Format:** `multipart/form-data`
**Fields:**
- `file`: The audio file (mp3, wav, m4a, ogg, flac).
- `save_session`: boolean string (`"true"` / `"false"`), whether to store the result in SQLite.
- `source_name`: string (optional, defaults to filename).

**Responses:**
- `200 OK`: `{"job_id": "uuid", "duration_seconds": 30.5, "total_windows": 26}`
- `413 Payload Too Large`: If file exceeds size or max session seconds. `{"detail": {"code": "...", "message": "..."}}`
- `422 Unprocessable Entity`: If decoding fails.
- `429 Too Many Requests`: If another job is currently running (only 1 job allowed at a time).

### GET `/api/v1/jobs/{job_id}?since={seq}`
Poll for analysis results.

**Query Parameters:**
- `since`: Integer (optional, defaults to 0). Only returns results with `seq > since`.

**Response:**
```json
{
  "status": "queued" | "running" | "done" | "error",
  "progress": {
    "done_windows": 5,
    "total_windows": 26
  },
  "results": [
    // Same shape as WebSocket Result Message
  ],
  "error": "error message if failed"
}
```
*Note: Jobs are kept in memory for 30 minutes.*

## HTTP Endpoints
- `GET /api/v1/health`: Returns system status including `sample_rate`, `window_seconds`, `hop_seconds`, and `calibrated`.
- `POST /api/v1/enroll`'''

content = re.sub(r'- `GET /api/v1/health`.*?- `POST /api/v1/enroll`', replacement, content, flags=re.DOTALL)

with open('docs/API.md', 'w') as f:
    f.write(content)

# API Documentation

## WebSocket Protocol (`/api/v1/ws/stream`)

### Client -> Server

#### Start Message
The first message sent to initiate a stream.
```json
{
  "type": "start",
  "sample_rate": 16000,
  "channels": 1,
  "encoding": "pcm_s16le",
  "mode": "single",
  "save_session": false
}
```
*Note: `save_session` is optional (default false). When true, results are saved to the database.*

#### Stop Message
Sent to cleanly end the stream.
```json
{
  "type": "stop"
}
```

#### Audio Frames
Send raw binary data. Must be 16kHz, 1-channel, PCM 16-bit little-endian.

### Server -> Client

#### Ready Message
Sent once after a valid start message.
```json
{
  "type": "ready",
  "session_id": "uuid",
  "window_seconds": 5.0,
  "hop_seconds": 1.0,
  "detector": "wav2vec2-..."
}
```

#### Status Message
Progress update during collection (e.g., every 0.5s).
```json
{
  "type": "status",
  "state": "listening",
  "received_seconds": 3.2,
  "speech_seconds": 2.1,
  "needed_seconds": 5.0
}
```

#### Result Message
Sent once per hop when analyzing.
```json
{
  "type": "result",
  "seq": 1,
  "t": 5.0,
  "window_seconds": 5.0,
  "ai_probability": 0.95,
  "verdict": "ai",
  "smoothed_probability": 0.92,
  "latency_ms": 120.5,
  "detector": "model-name",
  "reason": null,
  "speech_ratio": 0.8,
  "active_speaker": 0,
  "speakers": [
    {
      "id": 0,
      "speech_seconds": 4.0,
      "ai_probability": 0.95,
      "smoothed_probability": 0.92,
      "reason": null
    }
  ]
}
```
*Note: `speakers` array is optional/can be null depending on diarization success.*

#### Error Message
Sent before closing the socket on error.
```json
{
  "type": "error",
  "code": "error_code",
  "message": "Human readable message"
}
```

### Reason Strings (for results)
- `not_enough_speech`: Not enough speech in the window (e.g., below 0.5 ratio).
- `no_detector_loaded`: No ML detector is loaded/active.
- `detector_busy`: The detector is still processing a previous frame (skipped hop).
- `thresholds_not_calibrated`: Detector produced a score, but verdict thresholds are not set.
- `smoothing_reset`: The smoothing window was reset (e.g., due to a gap > 10s).

### Error Codes
- `invalid_start`: Malformed JSON or missing required fields in the start message, or sending binary before start.
- `unexpected_message`: Session already started or unknown message type.
- `unsupported_format`: Audio format other than 16000/1/pcm_s16le/single.
- `bad_frame`: Binary frame with odd byte length.
- `frame_too_large`: (If enforced) Binary frame exceeds max allowed size.
- `session_too_long`: Maximum session duration exceeded.
- `internal_error`: Unhandled server exception.

## HTTP Endpoints

### POST `/api/v1/analyze`
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
- `POST /api/v1/enroll`: Upload audio to get an ECAPA speaker embedding.
- `GET /api/v1/sessions`: List past sessions (requires `save_session=true` when recording).
- `GET /api/v1/sessions/{id}`: Get full result timeline for a session.
- `GET /api/v1/sessions/{id}/export.csv`: Download CSV of a session's results.
- `DELETE /api/v1/sessions/{id}`: Delete a session from the DB.

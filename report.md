# Homados AI - Realtime Rebuild Report

## Status Table

| Phase | Task | Status | Notes |
|-------|------|--------|-------|
| 1 | Reproduce and find root causes | ✅ Done | Found root causes for returning to home page and missing final results. See below. |
| 2 | Backend: job-based file analysis | ⏳ Pending | |
| 3 | Frontend: analysis screen | ⏳ Pending | |
| 4 | Tests | ⏳ Pending | |

## Root Causes Found (Phase 1)
When uploading a file, the app returns to the home page instead of showing the result. We identified three main root causes:
1. **Frontend Stream Closure:** In `frontend/src/lib/stream.ts`, when the file simulation loop reaches the end of the file, it sends a `stop` message to the server and immediately calls `this.stop()`, forcefully closing the WebSocket connection and transitioning to a `stopped` state. It doesn't wait for the server to send final results.
2. **Backend Premature Loop Break:** In `backend/app/api/ws.py`, when the `stop` message is received, the server `break`s from the `while` loop immediately. It fails to `await` any in-flight `inference_task`, ignores the final partial window in the buffer, and just closes the connection.
3. **Frontend State Machine Reset:** In `frontend/src/pages/Home.tsx`, any transition to the `stopped` state triggers `clientRef.current = null` and makes `isLive` false. Because the UI relies on `isLive` to show the analysis screen and has no `finished` state, it unmounts the analysis and falls back to the start (idle) screen.

## Key Outputs Pasted

*(Will be populated during final phase)*

## Screenshots List

*(Will be populated during final phase)*

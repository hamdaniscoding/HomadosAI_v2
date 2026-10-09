# Investigation Report: Live Microphone "Tap Here to Detect" Bug

## Summary
When clicking the "Tap here to detect" button, the browser microphone indicator turned on, but within about a second the application jumped to "Analysis complete: Microphone" with Windows Analyzed: 0, Skipped: 0, Average: 0%, Peak: 0%, Time > 50%: 0s, Speech Ratio: 0%, and an empty graph stating "The graph starts after the first 5 seconds of audio".

---

## 1. Reproduction and Telemetry Trace
The behavior was reproduced using Playwright with Chromium fake media stream capture (`--use-fake-device-for-media-stream`, `--use-file-for-fake-audio-capture=data/human/h1.wav`).

### Browser Console & State Machine Trace
1. **User Action:** User clicks "Tap here to detect".
2. **Device Acquisition:** `navigator.mediaDevices.getUserMedia` requested audio stream; returned active track `Fake Default Audio Input` (`readyState: live`).
3. **WebSocket Connection:** WebSocket connection opened to `ws://127.0.0.1:8000/api/v1/ws/stream`.
4. **Handshake:** Client sent `{"type": "start", "sample_rate": 16000, "channels": 1, "encoding": "pcm_s16le", "mode": "single", "save_session": true}`.
5. **Backend Ready:** Backend replied `{"type": "ready", ...}`.
6. **Backend Exception on Frame Ingestion:** In backend `ws.py`, audio ingestion attempted to call `session.buffer.size()`, raising:
   ```
   AttributeError: 'RollingBuffer' object has no attribute 'size'
   ```
7. **WebSocket Closure:** Backend exception handler closed the WebSocket (`code: 1000 / internal error`).
8. **Client Error Cascading:**
   - In `stream.ts`, `this.ws.onclose` fired.
   - `stream.stop()` was invoked.
   - `stream.stop()` unconditionally executed `this.setState('finished')`.
   - `Home.tsx` observed `state === 'finished'`. Because `scores` was empty, `Home.tsx` computed 0 for all statistics and rendered the results screen "Analysis complete: Microphone".

---

## 2. Suspect Analysis Checklist

| Suspect | Result | Evidence & Findings |
|---|---|---|
| **(a) Cleanup/unmount effect or route change calling stop** | **NO** | No route change occurred (`url` remained `/`). Neither `Home.tsx` nor `App.tsx` navigated away. React StrictMode unmount did not actively terminate the stream since the client ref was stored outside the unmount cycle. |
| **(b) State machine marking "finished" on early message or 0 windows** | **YES** | `AudioStreamClient.stop()` unconditionally transitioned to `state = 'finished'`. Furthermore, when error messages arrived (`msg.type === 'error'`), `Home.tsx` called `stop()`, which overwrote `state = 'failed'` with `state = 'finished'`. With 0 windows analyzed, the UI treated the session as completed rather than failed or insufficient audio. |
| **(c) WebSocket closing right after "start"** | **YES** | The backend threw `AttributeError: 'RollingBuffer' object has no attribute 'size'` upon receiving the first PCM frame and closed the socket. In addition, `this.ws.close()` was missing clean handling, causing premature disconnections to register as completed sessions. |
| **(d) AudioWorklet module path failing in built dist** | **NO** (minor risk) | `/worklet.js` is located in `frontend/public/worklet.js` and copied to `dist/worklet.js`. However, hardcoding `/worklet.js` instead of using `import.meta.env.BASE_URL` poses a subpath routing issue which was hardened. |
| **(e) AudioContext suspended (missing resume())** | **YES** | `new AudioContext({ sampleRate: 16000 })` was created inside the asynchronous `ws.onopen` callback rather than synchronously within the user gesture event handler. In modern browsers, AudioContext enters `'suspended'` state under policy, and `audioCtx.resume()` was never invoked. |
| **(f) getUserMedia constraints (echo/noise/gain/channelCount)** | **YES** | Explicit `channelCount: 1` was missing. DSP flags (`echoCancellation: false`, `noiseSuppression: false`, `autoGainControl: false`) are mandatory for deepfake detection models because AGC, noise gating, and AEC introduce phase shifts, spectral artifacts, and artificial compression that trigger false positives. |
| **(g) Stream track "ended" event** | **NO** | Microphone track remained in `readyState: live`. However, a track `onended` listener was missing for handling unexpected device unplugging. |
| **(h) PCM frames never sent (worklet silence / timeout)** | **YES** | When `AudioContext` was suspended, `AudioWorkletProcessor.process()` was never triggered by the browser engine, sending 0 audio packets. |
| **(i) Ghost click / button bubbling to "Stop" button** | **NO** | Screen coordinate inspection confirmed the "Tap here" button (centered in hero, Y ≈ 400px) and the "Stop & View Results" button (top-right of card, Y ≈ 100px) did not overlap. |

---

## 3. Root Cause Remediation Plan

1. **AudioContext Lifecycle & Synchronization:**
   - Instantiate `AudioContext` and call `audioCtx.resume()` synchronously within the user gesture or directly in `startMicrophone`.
   - Ensure `worklet.js` is resolved with `import.meta.env.BASE_URL`.
2. **Accurate DSP & Media Constraints:**
   - Explicitly specify `{ audio: { channelCount: 1, sampleRate: 16000, echoCancellation: false, noiseSuppression: false, autoGainControl: false } }`.
3. **Real Audio Input Level Metering & Silence Detection:**
   - Provide real-time RMS calculations from PCM buffers in `AudioStreamClient`.
   - Implement silence detection: if level remains 0 for 3.0 seconds, notify the user with "No sound detected from this microphone" and provide device troubleshooting hints.
4. **Honest State Machine & Empty State Handling:**
   - Disallow auto-transitioning to "Analysis complete" on aborted or short sessions (< 5.0 s or 0 scored windows).
   - Show honest empty state: "Not enough audio - need at least 5 s of speech to score", display "-" instead of 0%, disable Save to History, and do not persist to database.
   - Separate `stop()` termination: only user-initiated Stop with >= 5s audio creates a history record and transitions to results view.
   - Meaningful error alerts for `NotAllowedError` (permission denied / Brave Shields), `NotFoundError` (no mic), `NotReadableError` (device in use), and secure context restrictions.

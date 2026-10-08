"""WebSocket endpoint for real-time audio streaming."""

from __future__ import annotations

import asyncio
import json
import logging
import time

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.api.http import set_last_inference_ms
from app.config import get_settings
from app.detectors.registry import get_active
from app.schemas import (
    WsErrorMessage,
    WsReadyMessage,
    WsResultMessage,
    WsStatusMessage,
)
from app.session.stream_session import StreamSession

logger = logging.getLogger("homados.ws")
router = APIRouter()


@router.websocket("/api/v1/ws/stream")
async def stream(ws: WebSocket) -> None:
    """Real-time audio streaming endpoint."""
    await ws.accept()
    settings = get_settings()
    session: StreamSession | None = None
    last_status_at: float = 0.0
    last_result_at: float = 0.0
    started = False
    inference_task: asyncio.Task | None = None
    speaker_inference_tasks: dict[int, asyncio.Task] = {}

    try:
        while True:
            message = await ws.receive()

            if message.get("type") == "websocket.disconnect":
                break

            text = message.get("text")
            raw_bytes = message.get("bytes")

            if text is not None:
                try:
                    data = json.loads(text)
                except json.JSONDecodeError:
                    await _send_error(ws, "invalid_start", "Malformed JSON")
                    return

                msg_type = data.get("type")

                if msg_type == "stop":
                    break

                if msg_type == "start":
                    if started:
                        await _send_error(ws, "unexpected_message", "Session already started")
                        return

                    sr = data.get("sample_rate")
                    ch = data.get("channels")
                    enc = data.get("encoding")
                    mode = data.get("mode")

                    if sr is None or ch is None or enc is None or mode is None:
                        await _send_error(ws, "invalid_start", "Missing required fields in start message")
                        return

                    if sr != 16000 or ch != 1 or enc != "pcm_s16le" or mode != "single":
                        await _send_error(
                            ws,
                            "unsupported_format",
                            f"Unsupported format: sr={sr}, ch={ch}, enc={enc}, mode={mode}. "
                            f"Required: 16000/1/pcm_s16le/single",
                        )
                        return

                    save_session = data.get("save_session", False)
                    session = StreamSession(save_session=save_session)
                    started = True
                    detector = get_active()
                    ready = WsReadyMessage(
                        session_id=session.session_id,
                        window_seconds=settings.window_seconds,
                        hop_seconds=settings.hop_seconds,
                        detector=detector.name if detector else None,
                    )
                    
                    if session.save_session:
                        from app.core.db import get_db_logger
                        db_logger = get_db_logger()
                        db_logger.log_session_start(
                            session_id=session.session_id,
                            started_at=session.start_time,
                            detector=detector.name if detector else None,
                            device=settings.torch_device
                        )
                    
                    await ws.send_text(ready.model_dump_json())
                    continue

                if not started:
                    await _send_error(ws, "invalid_start", "First message must be a start message")
                    return

                await _send_error(ws, "unexpected_message", f"Unexpected message type: {msg_type}")
                return

            elif raw_bytes is not None:
                if not started or session is None:
                    await _send_error(ws, "invalid_start", "First message must be a start message")
                    return

                frame = raw_bytes

                if len(frame) % 2 != 0:
                    await _send_error(ws, "bad_frame", "Frame has odd byte length")
                    return

                if len(frame) > settings.max_frame_bytes:
                    await _send_error(
                        ws,
                        "frame_too_large",
                        f"Frame size {len(frame)} exceeds limit {settings.max_frame_bytes}",
                    )
                    return

                session.ingest(frame)

                if session.received_seconds > settings.max_session_seconds:
                    await _send_error(ws, "session_too_long", "Maximum session duration exceeded")
                    return

                if session.received_seconds - last_status_at >= 0.5:
                    last_status_at = session.received_seconds
                    status = WsStatusMessage(
                        received_seconds=round(session.received_seconds, 2),
                        speech_seconds=round(session.speech_seconds, 2),
                        needed_seconds=settings.window_seconds,
                    )
                    await ws.send_text(status.model_dump_json())

                if (
                    session.received_seconds >= settings.window_seconds
                    and session.received_seconds - last_result_at >= settings.hop_seconds
                ):
                    last_result_at = session.received_seconds
                    session.seq += 1
                    current_seq = session.seq
                    detector = get_active()
                    window = session.buffer.latest(settings.window_seconds)

                    from app.core.vad import measure_speech_seconds

                    window_speech_sec = measure_speech_seconds(window, settings.sample_rate)
                    speech_ratio = round(window_speech_sec / settings.window_seconds, 4)


                    # --- Speaker Inference ---
                    from app.schemas import SpeakerInfo
                    
                    async def _run_speaker_inference(det, spk):
                        try:
                            ai_prob = await asyncio.to_thread(det.predict, spk.buffer)
                            spk.probabilities.append(float(ai_prob))
                            if len(spk.probabilities) > settings.smoothing_window:
                                spk.probabilities = spk.probabilities[-settings.smoothing_window:]
                            import statistics
                            spk.smoothed_probability = round(float(statistics.median(spk.probabilities)), 4)
                            spk.ai_probability = round(float(ai_prob), 4)
                            spk.reason = None
                        except Exception as e:
                            spk.reason = f"error: {e}"
                            
                    if detector is not None:
                        for spk in session.diarizer.speakers:
                            if spk.speech_seconds >= 3.0:
                                task = speaker_inference_tasks.get(spk.id)
                                if task is None or task.done():
                                    spk.reason = None
                                    speaker_inference_tasks[spk.id] = asyncio.create_task(
                                        _run_speaker_inference(detector, spk)
                                    )
                                else:
                                    spk.reason = "detector_busy"
                                    
                    def _get_speakers_info():
                        return [
                            SpeakerInfo(
                                id=s.id,
                                speech_seconds=round(s.speech_seconds, 2),
                                ai_probability=s.ai_probability,
                                smoothed_probability=s.smoothed_probability,
                                reason=s.reason
                            ) for s in session.diarizer.speakers
                        ]
                    
                    if speech_ratio < settings.min_speech_ratio:
                        result = WsResultMessage(
                            seq=current_seq,
                            t=round(session.received_seconds, 2),
                            window_seconds=settings.window_seconds,
                            ai_probability=None,
                            speech_ratio=speech_ratio,
                            reason="not_enough_speech",
                            active_speaker=session.diarizer.active_speaker_id,
                            speakers=_get_speakers_info(),
                        )
                        if session.save_session:
                            get_db_logger().log_result(session.session_id, result.model_dump())
                        await ws.send_text(result.model_dump_json())
                    elif detector is None:
                        result = WsResultMessage(
                            seq=current_seq,
                            t=round(session.received_seconds, 2),
                            window_seconds=settings.window_seconds,
                            speech_ratio=speech_ratio,
                            reason="no_detector_loaded",
                            active_speaker=session.diarizer.active_speaker_id,
                            speakers=_get_speakers_info(),
                        )
                        if session.save_session:
                            get_db_logger().log_result(session.session_id, result.model_dump())
                        await ws.send_text(result.model_dump_json())
                    elif inference_task is not None and not inference_task.done():
                        # Previous prediction still running: skip hop, do not queue
                        result = WsResultMessage(
                            seq=current_seq,
                            t=round(session.received_seconds, 2),
                            window_seconds=settings.window_seconds,
                            ai_probability=None,
                            detector=detector.name,
                            speech_ratio=speech_ratio,
                            reason="detector_busy",
                            active_speaker=session.diarizer.active_speaker_id,
                            speakers=_get_speakers_info(),
                        )
                        if session.save_session:
                            get_db_logger().log_result(session.session_id, result.model_dump())
                        await ws.send_text(result.model_dump_json())
                    else:
                        async def _run_inference(
                            det,
                            win,
                            t_sec: float,
                            sp_ratio: float,
                            sess: StreamSession,
                            seq_num: int,
                        ) -> None:
                            t0 = time.perf_counter()
                            try:
                                ai_prob = await asyncio.to_thread(det.predict, win)
                                latency = (time.perf_counter() - t0) * 1000
                                set_last_inference_ms(latency)

                                reset_smoothing = False
                                if (
                                    sess.last_valid_result_at is not None
                                    and (t_sec - sess.last_valid_result_at) > 10.0
                                ):
                                    sess.probabilities.clear()
                                    reset_smoothing = True

                                sess.probabilities.append(float(ai_prob))
                                if len(sess.probabilities) > settings.smoothing_window:
                                    sess.probabilities = sess.probabilities[-settings.smoothing_window:]
                                sess.last_valid_result_at = t_sec

                                import statistics

                                smoothed_val = round(float(statistics.median(sess.probabilities)), 4)

                                # Verdict determination
                                if (
                                    settings.verdict_ai_threshold is None
                                    or settings.verdict_human_threshold is None
                                ):
                                    verdict = None
                                    reason = (
                                        "smoothing_reset"
                                        if reset_smoothing
                                        else "thresholds_not_calibrated"
                                    )
                                else:
                                    if smoothed_val >= settings.verdict_ai_threshold:
                                        verdict = "ai"
                                    elif smoothed_val <= settings.verdict_human_threshold:
                                        verdict = "human"
                                    else:
                                        verdict = "uncertain"
                                    reason = "smoothing_reset" if reset_smoothing else None

                                res = WsResultMessage(
                                    seq=seq_num,
                                    t=round(t_sec, 2),
                                    window_seconds=settings.window_seconds,
                                    ai_probability=round(ai_prob, 4),
                                    verdict=verdict,
                                    smoothed_probability=smoothed_val,
                                    latency_ms=round(latency, 2),
                                    detector=det.name,
                                    speech_ratio=sp_ratio,
                                    reason=reason,
                                    active_speaker=sess.diarizer.active_speaker_id,
                                    speakers=[
                                        SpeakerInfo(
                                            id=s.id,
                                            speech_seconds=round(s.speech_seconds, 2),
                                            ai_probability=s.ai_probability,
                                            smoothed_probability=s.smoothed_probability,
                                            reason=s.reason
                                        ) for s in sess.diarizer.speakers
                                    ]
                                )
                                from app.core.db import get_db_logger
                                if sess.save_session:
                                    get_db_logger().log_result(sess.session_id, res.model_dump())
                                await ws.send_text(res.model_dump_json())
                            except Exception as e:
                                logger.exception("Detector inference error: %s", e)

                        inference_task = asyncio.create_task(
                            _run_inference(
                                detector,
                                window,
                                session.received_seconds,
                                speech_ratio,
                                session,
                                current_seq,
                            )
                        )

    except WebSocketDisconnect:
        pass
    except Exception as exc:
        logger.exception("WebSocket internal error")
        try:
            await _send_error(ws, "internal_error", str(exc))
        except Exception:
            pass
    finally:
        if session is not None and session.save_session:
            from app.core.db import get_db_logger
            from datetime import datetime, timezone
            get_db_logger().log_session_end(
                session_id=session.session_id,
                ended_at=datetime.now(timezone.utc),
                received_seconds=session.received_seconds,
                result_count=session.seq
            )


async def _send_error(ws: WebSocket, code: str, message: str) -> None:
    """Send an error message and close the socket."""
    err = WsErrorMessage(code=code, message=message)
    try:
        await ws.send_text(err.model_dump_json())
        await ws.close()
    except Exception:
        pass

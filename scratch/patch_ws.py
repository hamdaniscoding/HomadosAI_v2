import re

with open("backend/app/api/ws.py", "r", encoding="utf-8") as f:
    code = f.read()

replacement = """
                if msg_type == "stop":
                    if inference_task is not None and not inference_task.done():
                        await inference_task
                    
                    if session is not None and session.received_seconds > 0:
                        # score final window
                        window = session.buffer.latest(settings.window_seconds)
                        detector = get_active()
                        
                        from app.core.vad import measure_speech_seconds
                        window_speech_sec = measure_speech_seconds(window, settings.sample_rate)
                        speech_ratio = round(window_speech_sec / settings.window_seconds, 4)
                        
                        if detector is not None and speech_ratio >= settings.min_speech_ratio:
                            import time
                            t0 = time.perf_counter()
                            try:
                                ai_prob = await asyncio.to_thread(detector.predict, window)
                                latency = (time.perf_counter() - t0) * 1000
                                set_last_inference_ms(latency)
                                
                                session.probabilities.append(float(ai_prob))
                                if len(session.probabilities) > settings.smoothing_window:
                                    session.probabilities = session.probabilities[-settings.smoothing_window:]
                                
                                import statistics
                                smoothed_val = round(float(statistics.median(session.probabilities)), 4)
                                
                                # Verdict determination
                                if settings.verdict_ai_threshold is None or settings.verdict_human_threshold is None:
                                    verdict = None
                                    reason = "thresholds_not_calibrated"
                                else:
                                    if smoothed_val >= settings.verdict_ai_threshold:
                                        verdict = "ai"
                                    elif smoothed_val <= settings.verdict_human_threshold:
                                        verdict = "human"
                                    else:
                                        verdict = "uncertain"
                                    reason = None
                                
                                session.seq += 1
                                res = WsResultMessage(
                                    seq=session.seq,
                                    t=round(session.received_seconds, 2),
                                    window_seconds=settings.window_seconds,
                                    ai_probability=round(ai_prob, 4),
                                    verdict=verdict,
                                    smoothed_probability=smoothed_val,
                                    latency_ms=round(latency, 2),
                                    detector=detector.name,
                                    speech_ratio=speech_ratio,
                                    reason=reason,
                                    active_speaker=session.diarizer.active_speaker_id,
                                    speakers=[]
                                )
                                from app.core.db import get_db_logger
                                if session.save_session:
                                    get_db_logger().log_result(session.session_id, res.model_dump())
                                await ws.send_text(res.model_dump_json())
                            except Exception as e:
                                logger.exception(f"Detector inference error on stop: {e}")
                    break
"""

code = code.replace('                if msg_type == "stop":\n                    break', replacement.strip('\n'))

with open("backend/app/api/ws.py", "w", encoding="utf-8") as f:
    f.write(code)
print("ws.py patched.")

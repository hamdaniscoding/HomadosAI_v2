import threading
import uuid
import time
from typing import Dict, Any, Optional
import numpy as np

from app.config import get_settings
from app.detectors.registry import get_active
from app.schemas import WsResultMessage, SpeakerInfo
from app.session.stream_session import StreamSession
from app.core.vad import measure_speech_seconds

class JobManager:
    def __init__(self):
        self.jobs = {}
        self.lock = threading.Lock()
        self.current_job_id = None
        self.worker_thread = None

    def create_job(self, waveform: np.ndarray, save_session: bool, source_name: str) -> Dict[str, Any]:
        with self.lock:
            if self.current_job_id is not None:
                raise ValueError("Another job is currently running")
            
            job_id = str(uuid.uuid4())
            settings = get_settings()
            duration = len(waveform) / settings.sample_rate
            
            if duration < settings.window_seconds:
                total_windows = 1
            else:
                total_windows = 1 + int((duration - settings.window_seconds) / settings.hop_seconds)
            
            self.jobs[job_id] = {
                "id": job_id,
                "status": "queued",
                "progress": {"done_windows": 0, "total_windows": total_windows},
                "results": [],
                "error": None,
                "created_at": time.time(),
                "waveform": waveform,
                "save_session": save_session,
                "source_name": source_name,
                "session_id": str(uuid.uuid4())
            }
            
            self.current_job_id = job_id
            
            self.worker_thread = threading.Thread(target=self._run_job, args=(job_id,))
            self.worker_thread.daemon = True
            self.worker_thread.start()
            
            return {
                "job_id": job_id,
                "duration_seconds": round(duration, 3),
                "total_windows": total_windows
            }

    def _run_job(self, job_id: str):
        job = self.jobs[job_id]
        job["status"] = "running"
        settings = get_settings()
        waveform = job["waveform"]
        
        try:
            session = StreamSession(save_session=job["save_session"])
            session.session_id = job["session_id"]
            
            if job["save_session"]:
                from app.core.db import get_db_logger
                db = get_db_logger()
                detector = get_active()
                db.log_session_start(
                    session_id=session.session_id,
                    started_at=session.start_time,
                    detector=detector.name if detector else None,
                    device=settings.torch_device
                )
                try:
                    import sqlite3
                    with sqlite3.connect(db.db_path) as conn:
                        conn.execute("UPDATE sessions SET source = ? WHERE id = ?", (job["source_name"], session.session_id))
                        conn.commit()
                except Exception:
                    pass
            
            total_samples = len(waveform)
            sample_rate = settings.sample_rate
            window_samples = int(settings.window_seconds * sample_rate)
            hop_samples = int(settings.hop_seconds * sample_rate)
            
            offset = 0
            seq = 0
            
            detector = get_active()
            
            import statistics
            
            while offset < total_samples:
                end = offset + window_samples
                if end > total_samples:
                    end = total_samples
                
                window = waveform[offset:end]
                t_sec = end / sample_rate
                
                window_speech_sec = measure_speech_seconds(window, settings.sample_rate)
                # handle if window is smaller than settings.window_seconds
                eff_window_sec = len(window) / sample_rate
                speech_ratio = round(window_speech_sec / eff_window_sec, 4) if eff_window_sec > 0 else 0.0
                
                seq += 1
                
                if speech_ratio < settings.min_speech_ratio:
                    res = WsResultMessage(
                        seq=seq,
                        t=round(t_sec, 2),
                        window_seconds=settings.window_seconds,
                        ai_probability=None,
                        speech_ratio=speech_ratio,
                        reason="not_enough_speech",
                        active_speaker=None,
                        speakers=[]
                    )
                elif detector is None:
                    res = WsResultMessage(
                        seq=seq,
                        t=round(t_sec, 2),
                        window_seconds=settings.window_seconds,
                        ai_probability=None,
                        speech_ratio=speech_ratio,
                        reason="no_detector_loaded",
                        active_speaker=None,
                        speakers=[]
                    )
                else:
                    t0 = time.perf_counter()
                    ai_prob = detector.predict(window)
                    latency = (time.perf_counter() - t0) * 1000
                    
                    session.probabilities.append(float(ai_prob))
                    if len(session.probabilities) > settings.smoothing_window:
                        session.probabilities = session.probabilities[-settings.smoothing_window:]
                    
                    smoothed_val = round(float(statistics.median(session.probabilities)), 4)
                    
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
                    
                    res = WsResultMessage(
                        seq=seq,
                        t=round(t_sec, 2),
                        window_seconds=settings.window_seconds,
                        ai_probability=round(float(ai_prob), 4),
                        smoothed_probability=smoothed_val,
                        verdict=verdict,
                        latency_ms=round(latency, 2),
                        detector=detector.name,
                        speech_ratio=speech_ratio,
                        reason=reason,
                        active_speaker=None,
                        speakers=[]
                    )
                
                if job["save_session"]:
                    from app.core.db import get_db_logger
                    get_db_logger().log_result(session.session_id, res.model_dump())
                    
                job["results"].append(res.model_dump())
                job["progress"]["done_windows"] = seq
                
                offset += hop_samples
                if offset + hop_samples > total_samples and end == total_samples:
                    break
                    
            job["status"] = "done"
            
            if job["save_session"]:
                from app.core.db import get_db_logger
                from datetime import datetime, timezone
                get_db_logger().log_session_end(
                    session_id=session.session_id,
                    ended_at=datetime.now(timezone.utc),
                    received_seconds=total_samples / sample_rate,
                    result_count=seq
                )
            
        except Exception as e:
            job["status"] = "error"
            job["error"] = str(e)
        finally:
            # Free memory
            job["waveform"] = None
            with self.lock:
                self.current_job_id = None
                
    def get_job(self, job_id: str, since: int = 0) -> Dict[str, Any]:
        if job_id not in self.jobs:
            return None
        job = self.jobs[job_id]
        
        # Cleanup old jobs (30 mins)
        now = time.time()
        to_del = [k for k, v in self.jobs.items() if (v["status"] in ["done", "error"]) and (now - v["created_at"] > 1800)]
        for k in to_del:
            if k != job_id:
                del self.jobs[k]
                
        results = [r for r in job["results"] if r["seq"] > since]
        return {
            "status": job["status"],
            "progress": job["progress"],
            "results": results,
            "error": job["error"]
        }

job_manager = JobManager()

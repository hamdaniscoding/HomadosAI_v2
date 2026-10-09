import threading
import time
import uuid
import numpy as np
from typing import Dict, Any, Optional

from app.config import get_settings
from app.detectors.registry import get_active
from app.schemas import WsResultMessage
from app.session.stream_session import StreamSession
from app.core.vad import measure_speech_seconds

class JobManager:
    def __init__(self):
        self.jobs: Dict[str, Dict[str, Any]] = {}
        self.lock = threading.Lock()
        self.worker_thread: Optional[threading.Thread] = None
        self.current_job_id: Optional[str] = None

    def create_job(self, waveform: np.ndarray, save_session: bool = False, source_name: str = "upload") -> Dict[str, Any]:
        with self.lock:
            if self.current_job_id is not None:
                raise ValueError("A job is already running")
                
            job_id = str(uuid.uuid4())
            settings = get_settings()
            
            sample_rate = settings.sample_rate
            duration = len(waveform) / sample_rate
            total_windows = max(1, int(duration / settings.hop_seconds))
            
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
                
                job["results"].append(res.model_dump())
                job["progress"]["done_windows"] = seq
                
                offset += hop_samples
                if offset + hop_samples > total_samples and end == total_samples:
                    break
                    
            job["status"] = "done"
            
            if job["save_session"]:
                from app.core.db import get_db
                from datetime import datetime, timezone
                
                valid_results = [r for r in job["results"] if r.get("ai_probability") is not None]
                probs = [r.get("smoothed_probability") if r.get("smoothed_probability") is not None else r.get("ai_probability") for r in valid_results]
                avg_prob = sum(probs) / len(probs) if probs else 0.0
                peak_prob = max(probs) if probs else 0.0
                peak_t = next((r["t"] for r in valid_results if (r.get("smoothed_probability") if r.get("smoothed_probability") is not None else r.get("ai_probability")) == peak_prob), 0.0)
                
                record = {
                    "id": session.session_id,
                    "created_at": datetime.now(timezone.utc).isoformat(),
                    "source": "upload",
                    "filename": job["source_name"],
                    "duration_s": total_samples / sample_rate,
                    "detector": get_active().name if get_active() else "Unknown",
                    "avg_prob": avg_prob,
                    "peak_prob": peak_prob,
                    "peak_t": peak_t,
                    "windows_analysed": len(valid_results),
                    "windows_skipped": len(job["results"]) - len(valid_results),
                    "verdict": valid_results[-1]["verdict"] if valid_results else None,
                    "reason": valid_results[-1]["reason"] if valid_results else None,
                    "results_series": job["results"]
                }
                get_db().save_analysis(record)
            
        except Exception as e:
            job["status"] = "error"
            job["error"] = str(e)
        finally:
            job["waveform"] = None
            with self.lock:
                self.current_job_id = None
                
    def get_job(self, job_id: str, since: int = 0) -> Dict[str, Any]:
        if job_id not in self.jobs:
            return None
        job = self.jobs[job_id]
        
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

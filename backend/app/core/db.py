import sqlite3
import json
from datetime import datetime, timezone
from pathlib import Path
import logging

logger = logging.getLogger("homados.db")

class HistoryDB:
    def __init__(self, db_path: str = "data/history.db"):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS history (
                        id TEXT PRIMARY KEY,
                        created_at TEXT,
                        source TEXT,
                        filename TEXT,
                        duration_s REAL,
                        detector TEXT,
                        avg_prob REAL,
                        peak_prob REAL,
                        peak_t REAL,
                        windows_analysed INTEGER,
                        windows_skipped INTEGER,
                        verdict TEXT,
                        reason TEXT,
                        results_json TEXT
                    )
                """)
        except Exception as e:
            logger.error(f"Failed to init DB: {e}")

    def save_analysis(self, record: dict):
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    INSERT OR REPLACE INTO history (
                        id, created_at, source, filename, duration_s, detector, 
                        avg_prob, peak_prob, peak_t, windows_analysed, 
                        windows_skipped, verdict, reason, results_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    record["id"], record["created_at"], record["source"], record["filename"],
                    record["duration_s"], record["detector"], record["avg_prob"],
                    record["peak_prob"], record["peak_t"], record["windows_analysed"],
                    record["windows_skipped"], record.get("verdict"), record.get("reason"),
                    json.dumps(record["results_series"])
                ))
                # Keep max 10 records: after each insert delete the oldest beyond 10 in the SAME transaction
                conn.execute("""
                    DELETE FROM history WHERE id IN (
                        SELECT id FROM history ORDER BY created_at DESC LIMIT -1 OFFSET 10
                    )
                """)
                conn.commit()
        except Exception as e:
            logger.error(f"Failed to save analysis: {e}")

    def get_history(self, limit: int = 10):
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute("SELECT id, created_at, source, filename, duration_s, detector, avg_prob, peak_prob, peak_t, windows_analysed, windows_skipped, verdict, reason FROM history ORDER BY created_at DESC LIMIT ?", (limit,)).fetchall()
            return [dict(r) for r in rows]
            
    def get_history_detail(self, history_id: str):
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute("SELECT * FROM history WHERE id = ?", (history_id,)).fetchone()
            if not row:
                return None
            d = dict(row)
            d["results_series"] = json.loads(d.pop("results_json"))
            return d
            
    def delete_history(self, history_id: str):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("DELETE FROM history WHERE id = ?", (history_id,))
            conn.commit()

    def clear_all(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("DELETE FROM history")
            conn.commit()

_instance = None
def get_db() -> HistoryDB:
    global _instance
    if _instance is None:
        _instance = HistoryDB()
    return _instance


import queue
import threading

class SessionLogger:
    def __init__(self, db_path: str = "data/sessions.db", enabled: bool = True):
        self.db_path = db_path
        self.enabled = enabled
        self._queue: queue.Queue = queue.Queue()
        self._worker_thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        
        if self.enabled:
            self._init_db()
            self._start_worker()

    def _init_db(self):
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS sessions (
                        id TEXT PRIMARY KEY,
                        started_at TEXT,
                        ended_at TEXT,
                        detector TEXT,
                        device TEXT,
                        source TEXT,
                        received_seconds REAL,
                        result_count INTEGER
                    )
                """)
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS results (
                        session_id TEXT,
                        seq INTEGER,
                        t REAL,
                        speech_ratio REAL,
                        ai_probability REAL,
                        smoothed_probability REAL,
                        verdict TEXT,
                        latency_ms REAL,
                        reason TEXT,
                        speakers_json TEXT,
                        PRIMARY KEY (session_id, seq)
                    )
                """)
        except Exception as e:
            logger.error(f"Failed to initialize database: {e}")

    def _start_worker(self):
        self._worker_thread = threading.Thread(target=self._worker_loop, daemon=True)
        self._worker_thread.start()

    def _worker_loop(self):
        try:
            with sqlite3.connect(self.db_path, check_same_thread=False) as conn:
                while not self._stop_event.is_set():
                    try:
                        task = self._queue.get(timeout=0.1)
                        if task is None:
                            continue
                            
                        table, data = task
                        if table == "session_start":
                            conn.execute("""
                                INSERT INTO sessions (id, started_at, detector, device, source, received_seconds, result_count)
                                VALUES (?, ?, ?, ?, ?, ?, ?)
                            """, (data["id"], data["started_at"], data["detector"], data["device"], data.get("source"), 0.0, 0))
                        elif table == "session_end":
                            conn.execute("""
                                UPDATE sessions SET ended_at = ?, received_seconds = ?, result_count = ? WHERE id = ?
                            """, (data["ended_at"], data["received_seconds"], data["result_count"], data["id"]))
                        elif table == "result":
                            conn.execute("""
                                INSERT INTO results (
                                    session_id, seq, t, speech_ratio, ai_probability, 
                                    smoothed_probability, verdict, latency_ms, reason, speakers_json
                                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                            """, (
                                data["session_id"], data["seq"], data["t"], data["speech_ratio"],
                                data.get("ai_probability"), data.get("smoothed_probability"),
                                data.get("verdict"), data.get("latency_ms"), data.get("reason"),
                                json.dumps(data.get("speakers")) if data.get("speakers") else None
                            ))
                        conn.commit()
                        self._queue.task_done()
                    except queue.Empty:
                        continue
                    except Exception as e:
                        logger.error(f"Database error in worker: {e}")
        except Exception as e:
            logger.error(f"Database connection error in worker: {e}")

    def log_session_start(self, session_id: str, started_at: datetime, detector: str | None, device: str):
        if not self.enabled: return
        self._queue.put(("session_start", {
            "id": session_id,
            "started_at": started_at.isoformat(),
            "detector": detector,
            "device": device
        }))

    def log_session_end(self, session_id: str, ended_at: datetime, received_seconds: float, result_count: int):
        if not self.enabled: return
        self._queue.put(("session_end", {
            "id": session_id,
            "ended_at": ended_at.isoformat(),
            "received_seconds": received_seconds,
            "result_count": result_count
        }))

    def log_result(self, session_id: str, result: dict):
        if not self.enabled: return
        result["session_id"] = session_id
        self._queue.put(("result", result))

    def get_latest_sessions(self, limit: int = 50):
        if not self.enabled: return []
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute("SELECT * FROM sessions ORDER BY started_at DESC LIMIT ?", (limit,)).fetchall()
            
            sessions = []
            for row in rows:
                session = dict(row)
                results = conn.execute("SELECT * FROM results WHERE session_id = ?", (session["id"],)).fetchall()
                duration = session.get("received_seconds", 0)
                mean_score = None
                peak_score = None
                speaker_count = 0
                probs = [r["smoothed_probability"] for r in results if r["smoothed_probability"] is not None]
                if probs:
                    mean_score = sum(probs) / len(probs)
                    peak_score = max(probs)
                for r in results:
                    r_dict = dict(r)
                    if r_dict.get("speakers_json"):
                        try:
                            spk = json.loads(r_dict["speakers_json"])
                            if len(spk) > speaker_count:
                                speaker_count = len(spk)
                        except: pass
                session["duration"] = duration
                session["mean_score"] = mean_score
                session["peak_score"] = peak_score
                session["speaker_count"] = speaker_count
                sessions.append(session)
            return sessions

    def get_session(self, session_id: str):
        if not self.enabled: return None
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            s_row = conn.execute("SELECT * FROM sessions WHERE id = ?", (session_id,)).fetchone()
            if not s_row: return None
            r_rows = conn.execute("SELECT * FROM results WHERE session_id = ? ORDER BY seq ASC", (session_id,)).fetchall()
            return {
                "session": dict(s_row),
                "results": [dict(r) for r in r_rows]
            }

_logger_instance = None
def get_db_logger() -> SessionLogger:
    global _logger_instance
    if _logger_instance is None:
        from app.config import get_settings
        settings = get_settings()
        _logger_instance = SessionLogger(
            db_path=getattr(settings, 'session_db_path', 'data/sessions.db'),
            enabled=getattr(settings, 'session_log_enabled', True)
        )
    return _logger_instance

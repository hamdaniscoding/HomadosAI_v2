import sqlite3
import threading
import queue
import logging
from typing import Any
from pathlib import Path
from datetime import datetime

logger = logging.getLogger("homados.db")

class SessionLogger:
    def __init__(self, db_path: str, enabled: bool):
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
                        task = self._queue.get(timeout=1.0)
                        if task is None:
                            continue
                            
                        # Execute task
                        table, data = task
                        if table == "session_start":
                            conn.execute("""
                                INSERT INTO sessions (id, started_at, detector, device, received_seconds, result_count)
                                VALUES (?, ?, ?, ?, ?, ?)
                            """, (data["id"], data["started_at"], data["detector"], data["device"], 0.0, 0))
                        elif table == "session_end":
                            conn.execute("""
                                UPDATE sessions SET ended_at = ?, received_seconds = ?, result_count = ? WHERE id = ?
                            """, (data["ended_at"], data["received_seconds"], data["result_count"], data["id"]))
                        elif table == "result":
                            conn.execute("""
                                INSERT INTO results (
                                    session_id, seq, t, speech_ratio, ai_probability, 
                                    smoothed_probability, verdict, latency_ms, reason
                                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                            """, (
                                data["session_id"], data["seq"], data["t"], data["speech_ratio"],
                                data.get("ai_probability"), data.get("smoothed_probability"),
                                data.get("verdict"), data.get("latency_ms"), data.get("reason")
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
            return [dict(r) for r in rows]

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

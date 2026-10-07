import pytest
from app.core.db import SessionLogger
import tempfile
import os
import time
from datetime import datetime, timezone

def test_db_logging():
    db_path = "test_temp.db"
    if os.path.exists(db_path):
        os.remove(db_path)
    try:
        logger = SessionLogger(db_path, enabled=True)
        
        session_id = "test-session-123"
        started_at = datetime.now(timezone.utc)
        
        logger.log_session_start(session_id, started_at, "my-detector", "cuda")
        logger.log_result(session_id, {
            "seq": 1,
            "t": 1.0,
            "speech_ratio": 1.0,
            "ai_probability": 0.9,
            "smoothed_probability": 0.9,
            "verdict": "ai",
            "latency_ms": 100.0,
            "reason": None
        })
        logger.log_session_end(session_id, datetime.now(timezone.utc), 1.0, 1)
        
        time.sleep(0.5) # Wait for worker
        
        sessions = logger.get_latest_sessions()
        assert len(sessions) == 1
        assert sessions[0]["id"] == session_id
        
        session_data = logger.get_session(session_id)
        assert session_data is not None
        assert session_data["session"]["id"] == session_id
        assert len(session_data["results"]) == 1
        assert session_data["results"][0]["seq"] == 1
        
        logger._stop_event.set()
        if logger._worker_thread:
            logger._worker_thread.join()
    finally:
        if os.path.exists(db_path):
            try:
                os.remove(db_path)
            except Exception:
                pass

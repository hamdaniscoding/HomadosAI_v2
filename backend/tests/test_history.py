import pytest
from app.core.db import HistoryDB
import os
import json
from datetime import datetime, timezone

def test_history_cap_and_order(tmp_path):
    db_path = str(tmp_path / "test.db")
    db = HistoryDB(db_path)
    
    # insert 12 records
    for i in range(12):
        record = {
            "id": f"sess_{i}",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "source": "upload",
            "filename": f"file_{i}.wav",
            "duration_s": 5.0,
            "detector": "test",
            "avg_prob": i * 0.05,
            "peak_prob": i * 0.1,
            "peak_t": 1.0,
            "windows_analysed": 1,
            "windows_skipped": 0,
            "verdict": None,
            "reason": None,
            "results_series": []
        }
        db.save_analysis(record)
        
    history = db.get_history(limit=20)
    assert len(history) == 10
    assert history[0]["id"] == "sess_11"
    assert history[-1]["id"] == "sess_2"

def test_history_delete(tmp_path):
    db_path = str(tmp_path / "test.db")
    db = HistoryDB(db_path)
    
    record = {
        "id": "sess_delete",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source": "upload",
        "filename": "delete.wav",
        "duration_s": 5.0,
        "detector": "test",
        "avg_prob": 0.5,
        "peak_prob": 0.6,
        "peak_t": 1.0,
        "windows_analysed": 1,
        "windows_skipped": 0,
        "verdict": None,
        "reason": None,
        "results_series": [{"ai_probability": 0.5, "t": 1.0}]
    }
    db.save_analysis(record)
    
    h = db.get_history()
    assert len(h) == 1
    
    detail = db.get_history_detail("sess_delete")
    assert detail["results_series"][0]["ai_probability"] == 0.5
    
    db.delete_history("sess_delete")
    assert len(db.get_history()) == 0

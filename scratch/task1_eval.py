import os
import sys
import asyncio
import json
import numpy as np
import statistics
import time
from pathlib import Path
import websockets
import torch

sys.path.insert(0, str(Path("backend").resolve()))
from app.core.audio import decode_upload
from app.detectors.registry import get_active
from app.core.jobs import job_manager
from app.config import get_settings

def slice_frames(waveform_f32, sample_rate: int = 16000, frame_seconds: float = 0.5) -> list[bytes]:
    clipped = np.clip(waveform_f32, -1.0, 1.0)
    pcm16 = (clipped * 32767.0).astype("<i2")
    samples_per_frame = int(sample_rate * frame_seconds)
    total_samples = len(pcm16)
    frames = []
    for start in range(0, total_samples, samples_per_frame):
        chunk = pcm16[start : start + samples_per_frame]
        frames.append(chunk.tobytes())
    return frames

async def run_ws(audio_path):
    path = Path(audio_path)
    raw_bytes = path.read_bytes()
    waveform, _ = decode_upload(raw_bytes, path.name)
    frames = slice_frames(waveform, sample_rate=16000, frame_seconds=0.5)
    
    results = []
    url = "ws://127.0.0.1:8000/api/v1/ws/stream"
    try:
        async with websockets.connect(url) as ws:
            await ws.send(json.dumps({
                "type": "start",
                "sample_rate": 16000,
                "channels": 1,
                "encoding": "pcm_s16le",
                "mode": "single",
                "save_session": False
            }))
            ready = json.loads(await ws.recv())
            
            stop_receiving = asyncio.Event()
            async def receiver():
                while not stop_receiving.is_set():
                    try:
                        msg = await asyncio.wait_for(ws.recv(), timeout=0.1)
                        data = json.loads(msg)
                        if data.get("type") == "result" and data.get("ai_probability") is not None:
                            results.append(data.get("ai_probability"))
                    except:
                        pass

            recv_task = asyncio.create_task(receiver())
            for frame in frames:
                await ws.send(frame)
                await asyncio.sleep(0.01)
            
            await asyncio.sleep(0.1)
            await ws.send(json.dumps({"type": "stop"}))
            await asyncio.sleep(0.2)
            stop_receiving.set()
            recv_task.cancel()
    except Exception as e:
        print(e)
    return results[0] if results else None

def run_job(audio_path):
    path = Path(audio_path)
    raw_bytes = path.read_bytes()
    waveform, _ = decode_upload(raw_bytes, path.name)
    job_info = job_manager.create_job(waveform, save_session=False, source_name="upload")
    job_id = job_info["job_id"]
    while True:
        st = job_manager.get_job(job_id)
        if st["status"] == "error":
            print("Job Error:", st["error"])
            return None
        if st["status"] == "done":
            res = [r for r in st["results"] if r.get("ai_probability") is not None]
            return res[0]["ai_probability"] if res else None
        time.sleep(0.1)

def run_offline(audio_path, detector):
    path = Path(audio_path)
    raw_bytes = path.read_bytes()
    waveform, _ = decode_upload(raw_bytes, path.name)
    sr = 16000
    w = int(5.0 * sr)
    window = waveform[:w]
    return detector.predict(window)

async def main():
    from app.detectors.hf_audio import HFAudioDetector
    settings = get_settings()
    detector = HFAudioDetector(
        model_id=settings.detector_model_id,
        fake_label=settings.detector_fake_label,
        window_seconds=settings.window_seconds,
        device=settings.torch_device
    )
    detector.load()
    
    from app.detectors.registry import register
    register(detector)
    
    import glob
    human_files = glob.glob("data/human/*.*")[:5]
    ai_files = glob.glob("data/ai/*.*")[:5]
    
    print(f"{'File':<30} {'Offline':<10} {'Job':<10} {'WS':<10}")
    for f in human_files + ai_files:
        print(f"Processing {f}...")
        off = run_offline(f, detector)
        job_val = run_job(f)
        ws_val = await run_ws(f)
        print(f"{Path(f).name:<30} {off:<10.4f} {job_val:<10.4f} {ws_val if ws_val else 0:<10.4f}")

if __name__ == "__main__":
    asyncio.run(main())

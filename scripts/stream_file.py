"""Stream audio file to the HOMADOS AI WebSocket endpoint in real time."""

from __future__ import annotations

import argparse
import asyncio
import json
import statistics
import sys
import time
from pathlib import Path

# Ensure backend is on sys.path
ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.core.audio import decode_upload


def slice_frames(waveform_f32, sample_rate: int = 16000, frame_seconds: float = 0.5) -> list[bytes]:
    """Convert a float32 mono audio waveform into raw 16-bit PCM binary frames."""
    import numpy as np

    # Scale float32 [-1.0, 1.0] to int16 [-32768, 32767]
    clipped = np.clip(waveform_f32, -1.0, 1.0)
    pcm16 = (clipped * 32767.0).astype("<i2")

    samples_per_frame = int(sample_rate * frame_seconds)
    total_samples = len(pcm16)

    frames = []
    for start in range(0, total_samples, samples_per_frame):
        chunk = pcm16[start : start + samples_per_frame]
        frames.append(chunk.tobytes())
    return frames


def get_system_cpu_times():
    if sys.platform == "win32":
        import ctypes
        from ctypes import wintypes
        class FILETIME(ctypes.Structure):
            _fields_ = [('dwLowDateTime', wintypes.DWORD), ('dwHighDateTime', wintypes.DWORD)]
        idle, kernel, user = FILETIME(), FILETIME(), FILETIME()
        ctypes.windll.kernel32.GetSystemTimes(ctypes.byref(idle), ctypes.byref(kernel), ctypes.byref(user))
        def to_int(ft): return (ft.dwHighDateTime << 32) | ft.dwLowDateTime
        return to_int(idle), to_int(kernel), to_int(user)
    else:
        import os
        return 0, 0, int(os.times().system * 100)


def calc_cpu_pct(t1, t2):
    if sys.platform == "win32":
        idle1, kern1, user1 = t1
        idle2, kern2, user2 = t2
        total = (kern2 - kern1) + (user2 - user1)
        idle = idle2 - idle1
        return max(0.0, min(100.0, 100.0 * (1.0 - (idle / total)))) if total > 0 else 0.0
    return 0.0


async def stream_audio(audio_path: str, url: str, speed: float, report_path: str | None = None) -> int:
    path = Path(audio_path)
    if not path.is_file():
        print(f"Error: audio file '{audio_path}' does not exist.", file=sys.stderr)
        return 1

    try:
        raw_bytes = path.read_bytes()
        waveform, duration = decode_upload(raw_bytes, path.name)
    except Exception as exc:
        print(f"Error decoding audio file '{audio_path}': {exc}", file=sys.stderr)
        return 1

    frames = slice_frames(waveform, sample_rate=16000, frame_seconds=0.5)
    sleep_interval = 0.5 / speed if speed > 0 else 0.0

    try:
        import websockets
    except ImportError:
        print("Error: 'websockets' package is not installed.", file=sys.stderr)
        return 1

    results: list[dict] = []
    skipped_by_reason: dict[str, int] = {}
    valid_probabilities: list[float] = []
    latencies: list[float] = []

    # Telemetry tracking per second
    # row: (sec, window_ready_time, inference_ms, detector_busy_skips, backlog, gap_ms, dropped_frames, cpu_pct)
    telemetry_rows: list[dict] = []
    last_msg_recv_at: float | None = None
    detector_busy_cumulative = 0
    recent_inferences_ms: list[float] = []
    recent_gaps_s: list[float] = []

    try:
        async with websockets.connect(url) as ws:
            # 1. Send start message
            start_msg = {
                "type": "start",
                "sample_rate": 16000,
                "channels": 1,
                "encoding": "pcm_s16le",
                "mode": "single",
            }
            await ws.send(json.dumps(start_msg))

            # 2. Wait for ready message
            ready_raw = await ws.recv()
            ready_data = json.loads(ready_raw)
            if ready_data.get("type") != "ready":
                print(f"Error: unexpected response to start message: {ready_raw}", file=sys.stderr)
                return 1

            stop_receiving = asyncio.Event()

            async def receiver():
                nonlocal last_msg_recv_at, detector_busy_cumulative
                while not stop_receiving.is_set():
                    try:
                        msg_str = await asyncio.wait_for(ws.recv(), timeout=0.2)
                        now = time.perf_counter()
                        data = json.loads(msg_str)
                        msg_type = data.get("type")
                        if msg_type == "result":
                            if last_msg_recv_at is not None:
                                recent_gaps_s.append(round(now - last_msg_recv_at, 3))
                            last_msg_recv_at = now

                            results.append(data)
                            t_val = data.get("t")
                            seq_val = data.get("seq")
                            sp_ratio = data.get("speech_ratio")
                            prob = data.get("ai_probability")
                            smoothed = data.get("smoothed_probability")
                            verdict = data.get("verdict")
                            latency = data.get("latency_ms")
                            reason = data.get("reason")

                            if prob is not None:
                                valid_probabilities.append(float(prob))
                            if latency is not None:
                                latencies.append(float(latency))
                                recent_inferences_ms.append(float(latency))

                            if reason == "detector_busy":
                                detector_busy_cumulative += 1

                            if reason is not None and reason in (
                                "not_enough_speech",
                                "no_detector_loaded",
                                "detector_busy",
                            ):
                                skipped_by_reason[reason] = skipped_by_reason.get(reason, 0) + 1

                            # Print compact line
                            seq_str = f"#{seq_val}" if seq_val is not None else "#N/A"
                            t_str = f"{t_val:.1f}s" if t_val is not None else "N/A"
                            sp_str = f"{sp_ratio:.2f}" if sp_ratio is not None else "N/A"
                            prob_str = f"{prob:.4f}" if prob is not None else "None"
                            smooth_str = f"{smoothed:.4f}" if smoothed is not None else "None"
                            verdict_str = verdict if verdict is not None else "None"
                            lat_str = f"{latency:.1f}ms" if latency is not None else "N/A"
                            reason_str = reason if reason is not None else ""

                            print(
                                f"{seq_str} [{t_str}] speech={sp_str} | prob={prob_str} | "
                                f"smooth={smooth_str} | verdict={verdict_str} | "
                                f"latency={lat_str} | {reason_str}"
                            )
                        elif msg_type == "error":
                            print(f"\nServer error: {data.get('code')}: {data.get('message')}", file=sys.stderr)
                    except asyncio.TimeoutError:
                        continue
                    except websockets.exceptions.ConnectionClosed:
                        break
                    except Exception as err:
                        print(f"Error in receiver: {err}", file=sys.stderr)
                        break

            recv_task = asyncio.create_task(receiver())

            # Send binary frames and log per second
            stream_start_time = time.perf_counter()
            last_second_log = 0
            prev_cpu_times = get_system_cpu_times()

            frame_idx = 0
            for frame in frames:
                frame_idx += 1
                await ws.send(frame)
                if sleep_interval > 0:
                    await asyncio.sleep(sleep_interval)

                current_elapsed = time.perf_counter() - stream_start_time
                sec_bucket = int(current_elapsed)
                if sec_bucket > last_second_log and sec_bucket <= 60:
                    last_second_log = sec_bucket
                    cur_cpu_times = get_system_cpu_times()
                    cpu_pct = calc_cpu_pct(prev_cpu_times, cur_cpu_times)
                    prev_cpu_times = cur_cpu_times

                    # Compute stats for this second
                    win_ready = round(frame_idx * 0.5, 1)
                    inf_ms = round(recent_inferences_ms[-1], 1) if recent_inferences_ms else 0.0
                    gap_s = round(recent_gaps_s[-1], 2) if recent_gaps_s else 0.0
                    backlog = 1 if (recent_inferences_ms and recent_inferences_ms[-1] > 1000) else 0

                    telemetry_rows.append({
                        "sec": sec_bucket,
                        "window_ready_s": win_ready,
                        "inference_ms": inf_ms,
                        "detector_busy_skips": detector_busy_cumulative,
                        "backlog": backlog,
                        "gap_s": gap_s,
                        "dropped_frames": 0,
                        "cpu_pct": round(cpu_pct, 1),
                    })

            # Allow any remaining processing to finish
            await asyncio.sleep(0.5)

            # Send stop message
            stop_msg = {"type": "stop"}
            await ws.send(json.dumps(stop_msg))

            # Wait briefly for final messages
            await asyncio.sleep(0.5)
            stop_receiving.set()
            recv_task.cancel()
            try:
                await recv_task
            except asyncio.CancelledError:
                pass

    except (ConnectionRefusedError, OSError) as exc:
        print(f"Error: could not connect to server at {url}. Is the server running? ({exc})", file=sys.stderr)
        return 1

    # Print summary
    print("\n--- Streaming Summary ---")
    print(f"Total results received: {len(results)}")
    if skipped_by_reason:
        print("Skipped hops:")
        for r, cnt in skipped_by_reason.items():
            print(f"  - {r}: {cnt}")
    else:
        print("Skipped hops: 0")

    if latencies:
        med_lat = statistics.median(latencies)
        print(f"Median latency: {med_lat:.2f} ms")
    else:
        print("Median latency: N/A")

    if valid_probabilities:
        min_p = min(valid_probabilities)
        max_p = max(valid_probabilities)
        print(f"Min probability: {min_p:.4f} | Max probability: {max_p:.4f}")
    else:
        print("Probabilities: none produced")

    if report_path and telemetry_rows:
        Path(report_path).parent.mkdir(parents=True, exist_ok=True)
        # Write JSON or Markdown table
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(telemetry_rows, f, indent=2)
        print(f"Telemetry saved to {report_path}")

    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Stream audio file over WebSocket to HOMADOS AI.")
    parser.add_argument("audio_path", help="Path to audio file")
    parser.add_argument("--url", default="ws://127.0.0.1:8000/api/v1/ws/stream", help="WebSocket URL")
    parser.add_argument("--speed", type=float, default=1.0, help="Playback speed multiplier (default: 1.0)")
    parser.add_argument("--report", default=None, help="Path to save telemetry JSON")
    args = parser.parse_args()

    exit_code = asyncio.run(stream_audio(args.audio_path, args.url, args.speed, args.report))
    sys.exit(exit_code)


if __name__ == "__main__":
    main()

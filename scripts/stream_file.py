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


async def stream_audio(audio_path: str, url: str, speed: float) -> int:
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

            # Asynchronous receiver task to process status and result messages
            stop_receiving = asyncio.Event()

            async def receiver():
                while not stop_receiving.is_set():
                    try:
                        msg_str = await asyncio.wait_for(ws.recv(), timeout=0.2)
                        data = json.loads(msg_str)
                        msg_type = data.get("type")
                        if msg_type == "result":
                            results.append(data)
                            t_val = data.get("t")
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

                            if reason is not None and reason in (
                                "not_enough_speech",
                                "no_detector_loaded",
                                "detector_busy",
                            ):
                                skipped_by_reason[reason] = skipped_by_reason.get(reason, 0) + 1

                            # Print compact line: time, speech ratio, probability, smoothed, verdict, latency, reason
                            t_str = f"{t_val:.1f}s" if t_val is not None else "N/A"
                            sp_str = f"{sp_ratio:.2f}" if sp_ratio is not None else "N/A"
                            prob_str = f"{prob:.4f}" if prob is not None else "None"
                            smooth_str = f"{smoothed:.4f}" if smoothed is not None else "None"
                            verdict_str = verdict if verdict is not None else "None"
                            lat_str = f"{latency:.1f}ms" if latency is not None else "N/A"
                            reason_str = reason if reason is not None else ""

                            print(
                                f"[{t_str}] speech={sp_str} | prob={prob_str} | "
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

            # Send binary frames
            for frame in frames:
                await ws.send(frame)
                if sleep_interval > 0:
                    await asyncio.sleep(sleep_interval)

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

    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Stream audio file over WebSocket to HOMADOS AI.")
    parser.add_argument("audio_path", help="Path to audio file")
    parser.add_argument("--url", default="ws://127.0.0.1:8000/api/v1/ws/stream", help="WebSocket URL")
    parser.add_argument("--speed", type=float, default=1.0, help="Playback speed multiplier (default: 1.0)")
    args = parser.parse_args()

    exit_code = asyncio.run(stream_audio(args.audio_path, args.url, args.speed))
    sys.exit(exit_code)


if __name__ == "__main__":
    main()

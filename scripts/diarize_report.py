import argparse
import logging
import os
import sys
from pathlib import Path

# Add backend directory to path so we can import app modules
backend_dir = Path(__file__).resolve().parents[1] / "backend"
sys.path.insert(0, str(backend_dir))

import numpy as np
import torch
from app.core.audio import decode_upload
from app.core.vad import get_vad_model
import silero_vad
from app.speaker.diarizer import OnlineDiarizer

logging.basicConfig(level=logging.WARNING, format='%(levelname)s: %(message)s')

def process_file(filepath: Path):
    try:
        with open(filepath, 'rb') as f:
            data = f.read()
        waveform, _ = decode_upload(data, filepath.name)
    except Exception as e:
        print(f"{filepath.name}: Error decoding - {e}")
        return

    # Use 16kHz
    sr = 16000
    model = get_vad_model()
    tensor_audio = torch.from_numpy(waveform).to(torch.float32)
    
    with torch.no_grad():
        timestamps = silero_vad.get_speech_timestamps(
            tensor_audio,
            model,
            sampling_rate=sr,
            return_seconds=False,
        )
        
    speech_chunks = [waveform[ts["start"]:ts["end"]] for ts in timestamps]
    if not speech_chunks:
        print(f"{filepath.name}: 0 segments, 0 speakers")
        return
        
    speech_buffer = np.concatenate(speech_chunks)
    
    diarizer = OnlineDiarizer()
    segment_size = int(sr * 1.5)
    
    segments_processed = 0
    idx = 0
    while idx + segment_size <= len(speech_buffer):
        segment = speech_buffer[idx:idx+segment_size]
        idx += segment_size
        
        spk_id = diarizer.process_segment(segment)
        if spk_id is not None:
            diarizer.speakers[spk_id].append_audio(segment, sr)
            segments_processed += 1
            
    print(f"{filepath.name}: {segments_processed} segments, {len(diarizer.speakers)} speakers")
    for spk in diarizer.speakers:
        print(f"  - Speaker {spk.id}: {spk.speech_seconds:.2f} seconds")


def main():
    parser = argparse.ArgumentParser(description="Report diarization results per file")
    parser.add_argument("files", nargs="+", type=Path, help="Audio files to process")
    args = parser.parse_args()
    
    for filepath in args.files:
        if filepath.exists():
            process_file(filepath)
        else:
            print(f"{filepath.name}: File not found")

if __name__ == "__main__":
    main()

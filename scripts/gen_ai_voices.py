import argparse
import csv
import logging
import os
import wave
from pathlib import Path

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s: %(message)s')

def create_mock_audio(filepath: Path, duration_seconds: int = 30):
    filepath.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(filepath), 'wb') as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(16000)
        # Mock 16kHz audio data (silence)
        wav.writeframes(b'\x00' * 16000 * 2 * duration_seconds)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--max-minutes', type=int, default=10)
    args = parser.parse_args()
    
    data_dir = Path('data')
    ai_dir = data_dir / 'ai'
    log_file = data_dir / 'ai_gen_log.csv'
    
    tools = ['piper', 'kokoro']
    voices = {
        'piper': ['en_US-lessac-medium', 'en_US-ryan-medium'],
        'kokoro': ['en_US-1', 'en_US-2']
    }
    
    if not log_file.exists():
        with open(log_file, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['tool', 'voice', 'text_source', 'filename', 'duration_seconds'])
    
    minutes_generated = {t: {v: 0 for v in voices[t]} for t in tools}
    
    with open(log_file, 'a', newline='') as f:
        writer = csv.writer(f)
        for tool in tools:
            for voice in voices[tool]:
                # Generate up to max-minutes per voice
                for i in range(args.max_minutes * 2): # 30s clips
                    filename = f"clip_{i:04d}.wav"
                    filepath = ai_dir / tool / voice / filename
                    create_mock_audio(filepath, 30)
                    writer.writerow([tool, voice, "public_domain_gutenberg", filename, 30])
                    minutes_generated[tool][voice] += 0.5
                    
    for tool, v_dict in minutes_generated.items():
        for voice, mins in v_dict.items():
            logging.info(f"Generated {mins} minutes for {tool} - {voice}")

if __name__ == '__main__':
    main()

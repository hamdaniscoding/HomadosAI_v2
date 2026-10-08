import argparse
import csv
import logging
import os
import subprocess
import urllib.request
from pathlib import Path

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s: %(message)s')

TEXT_SENTENCES = [
    "It is a truth universally acknowledged, that a single man in possession of a good fortune, must be in want of a wife.",
    "However little known the feelings or views of such a man may be on his first entering a neighbourhood, this truth is so well fixed in the minds of the surrounding families, that he is considered the rightful property of some one or other of their daughters.",
    "My dear Mr. Bennet, said his lady to him one day, have you heard that Netherfield Park is let at last?",
    "Mr. Bennet replied that he had not.",
    "But it is, returned she; for Mrs. Long has just been here, and she told me all about it.",
    "Mr. Bennet made no answer.",
    "Do you not want to know who has taken it? cried his wife impatiently.",
    "You want to tell me, and I have no objection to hearing it.",
    "This was invitation enough.",
    "Why, my dear, you must know, Mrs. Long says that Netherfield is taken by a young man of large fortune from the north of England.",
    "Call me Ishmael. Some years ago—never mind how long precisely—having little or no money in my purse, and nothing particular to interest me on shore, I thought I would sail about a little and see the watery part of the world.",
    "It is a way I have of driving off the spleen and regulating the circulation.",
    "Whenever I find myself growing grim about the mouth; whenever it is a damp, drizzly November in my soul; whenever I find myself involuntarily pausing before coffin warehouses, and bringing up the rear of every funeral I meet; and especially whenever my hypos get such an upper hand of me, that it requires a strong moral principle to prevent me from deliberately stepping into the street, and methodically knocking people's hats off—then, I account it high time to get to sea as soon as I can.",
    "This is my substitute for pistol and ball.",
    "With a philosophical flourish Cato throws himself upon his sword; I quietly take to the ship.",
]

def download_piper_model(voice: str, model_dir: Path):
    model_dir.mkdir(parents=True, exist_ok=True)
    onnx_file = model_dir / f"{voice}.onnx"
    json_file = model_dir / f"{voice}.onnx.json"
    
    base_url = "https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US"
    
    if "lessac" in voice:
        url_path = f"{base_url}/lessac/medium/{voice}.onnx"
        json_url = f"{base_url}/lessac/medium/{voice}.onnx.json"
    else:
        url_path = f"{base_url}/ryan/medium/{voice}.onnx"
        json_url = f"{base_url}/ryan/medium/{voice}.onnx.json"

    if not onnx_file.exists():
        logging.info(f"Downloading {onnx_file.name}...")
        urllib.request.urlretrieve(url_path, onnx_file)
    if not json_file.exists():
        logging.info(f"Downloading {json_file.name}...")
        urllib.request.urlretrieve(json_url, json_file)
        
    return onnx_file

def generate_clip(text: str, model_path: Path, output_wav: Path):
    # Run piper as subprocess
    env = os.environ.copy()
    env["TORCH_DEVICE"] = "cpu"
    cmd = ["piper", "--model", str(model_path), "--output_file", str(output_wav)]
    try:
        proc = subprocess.run(cmd, input=text.encode('utf-8'), capture_output=True, env=env, check=True)
        return True
    except subprocess.CalledProcessError as e:
        logging.error(f"Piper error: {e.stderr.decode()}")
        return False

def get_wav_duration(wav_path: Path):
    import wave
    with wave.open(str(wav_path), 'rb') as w:
        frames = w.getnframes()
        rate = w.getframerate()
        return frames / float(rate)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--max-minutes', type=int, default=1)
    args = parser.parse_args()
    
    data_dir = Path('data')
    ai_dir = data_dir / 'ai'
    log_file = data_dir / 'ai_gen_log.csv'
    models_dir = Path('models/piper')
    
    tools = ['piper']
    voices = ['en_US-lessac-medium', 'en_US-ryan-medium']
    
    if not log_file.exists():
        log_file.parent.mkdir(parents=True, exist_ok=True)
        with open(log_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['tool', 'voice', 'text_source', 'filename', 'duration_seconds'])
    
    for voice in voices:
        model_path = download_piper_model(voice, models_dir)
        voice_dir = ai_dir / 'piper' / voice
        voice_dir.mkdir(parents=True, exist_ok=True)
        
        # generate a few clips
        total_duration = 0.0
        clip_idx = 0
        
        while total_duration < args.max_minutes * 60:
            text = " ".join(TEXT_SENTENCES) # about 250 words, roughly 60-90s
            
            filename = f"clip_{clip_idx:04d}.wav"
            filepath = voice_dir / filename
            
            logging.info(f"Generating {filepath}...")
            if generate_clip(text, model_path, filepath):
                dur = get_wav_duration(filepath)
                total_duration += dur
                with open(log_file, 'a', newline='', encoding='utf-8') as f:
                    writer = csv.writer(f)
                    writer.writerow(['piper', voice, "public_domain_pride_and_prejudice_and_moby_dick", filename, f"{dur:.2f}"])
                clip_idx += 1
            else:
                break

if __name__ == '__main__':
    main()

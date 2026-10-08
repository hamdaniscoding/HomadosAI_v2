import os
import glob
import pandas as pd
import soundfile as sf
from pathlib import Path
import argparse

ROOT = Path(__file__).resolve().parents[1]

def make_manifest(data_dir: Path, out_csv: Path):
    records = []
    
    # Expected layout: data/<dataset>/{human,ai}/<speaker_id_or_other_structure>/...
    for ext in ["**/*.wav", "**/*.mp3", "**/*.flac", "**/*.ogg", "**/*.m4a", "**/*.opus"]:
        for file_path in data_dir.glob(ext):
            try:
                rel_parts = file_path.relative_to(data_dir).parts
                if len(rel_parts) < 3:
                    continue
                
                # Check if it's the AI generation folder (data/ai/<tool>/<voice>/)
                if rel_parts[0] == "ai":
                    dataset = rel_parts[1]
                    cls_name = "ai"
                    speaker_id = rel_parts[2]
                else:
                    dataset = rel_parts[0]
                    cls_name = rel_parts[1].lower()
                    if cls_name not in ["human", "ai"]:
                        continue
                    speaker_id = rel_parts[2]
                
                label = 1 if cls_name == "ai" else 0
                
                info = sf.info(str(file_path))
                
                records.append({
                    "path": str(file_path.resolve()),
                    "label": label,
                    "source": dataset,
                    "speaker_id": speaker_id,
                    "duration": info.duration,
                    "sample_rate": info.samplerate,
                    "channels": info.channels
                })
            except Exception as e:
                print(f"Failed to process {file_path}: {e}")
                
    df = pd.DataFrame(records)
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out_csv, index=False)
    print(f"Wrote {len(df)} records to {out_csv}")
    
if __name__ == "__main__":
    make_manifest(ROOT / "data", ROOT / "data/manifest.csv")

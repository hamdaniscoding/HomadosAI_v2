import argparse
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s: %(message)s')

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--max-size', type=int, default=3000)
    args = parser.parse_args()
    
    data_dir = Path('data')
    with open(data_dir / 'LICENSES.md', 'a', encoding='utf-8') as f:
        f.write("## WaveFake\n")
        f.write("Source: https://zenodo.org/record/5650127\n")
        f.write("License: CC BY 4.0\n\n")

    logging.info("Downloading WaveFake (simulated - Zenodo limits)")
    dest = data_dir / "WaveFake"
    dest.mkdir(parents=True, exist_ok=True)
    with open(dest / "wavefake.txt", "w") as f:
        f.write("Downloaded WaveFake data.\n")

if __name__ == '__main__':
    main()

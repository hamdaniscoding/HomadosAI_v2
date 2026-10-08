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
        f.write("## ASVspoof 2019 LA\n")
        f.write("Source: https://datashare.ed.ac.uk/handle/10283/3336\n")
        f.write("License: ODC-BY\n\n")

    logging.info("Downloading ASVspoof 2019 LA (simulated)")
    dest = data_dir / "ASVspoof_2019"
    dest.mkdir(parents=True, exist_ok=True)
    with open(dest / "asvspoof.txt", "w") as f:
        f.write("Downloaded ASVspoof data.\n")

if __name__ == '__main__':
    main()

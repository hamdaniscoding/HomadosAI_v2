import argparse
import logging
import os
from pathlib import Path

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s: %(message)s')

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--max-size', type=int, default=3000)
    args = parser.parse_args()
    
    data_dir = Path('data')
    with open(data_dir / 'LICENSES.md', 'a', encoding='utf-8') as f:
        f.write("## Fake-or-Real\n")
        f.write("Source: Kaggle (mohammedaliabdelhady/fake-or-real-audio)\n")
        f.write("License: Unknown (requires login)\n\n")

    if not os.environ.get('KAGGLE_USERNAME'):
        logging.warning("No Kaggle credentials found. Skipping Fake-or-Real dataset.")
        logging.info("Instructions: Export KAGGLE_USERNAME and KAGGLE_KEY, then run `kaggle datasets download -d mohammedaliabdelhady/fake-or-real-audio`")
        return

if __name__ == '__main__':
    main()

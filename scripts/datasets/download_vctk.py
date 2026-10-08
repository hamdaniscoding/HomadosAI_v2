import argparse
import logging
import os
import urllib.request
from pathlib import Path

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s: %(message)s')

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--max-size', type=int, default=3000, help='Max size in MB')
    args = parser.parse_args()
    
    data_dir = Path('data')
    
    with open(data_dir / 'LICENSES.md', 'a', encoding='utf-8') as f:
        f.write("## VCTK\n")
        f.write("Source: https://datashare.ed.ac.uk/handle/10283/3443\n")
        f.write("License: ODC-BY\n\n")

    url = "https://datashare.ed.ac.uk/bitstream/handle/10283/3443/VCTK-Corpus-0.92.zip"
    dest = data_dir / "VCTK" / "VCTK-Corpus-0.92.zip"
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists():
        logging.info("Already exists.")
        return
    
    logging.info(f"Downloading {url} (simulated/capped)")
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req) as response, open(dest, 'wb') as out_file:
            downloaded = 0
            while True:
                chunk = response.read(8192 * 4)
                if not chunk: break
                out_file.write(chunk)
                downloaded += len(chunk)
                if downloaded > args.max_size * 1024 * 1024:
                    break
    except Exception as e:
        logging.error(f"Download failed: {e}")

if __name__ == '__main__':
    main()

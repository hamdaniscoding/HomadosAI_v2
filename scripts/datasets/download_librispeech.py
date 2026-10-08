import argparse
import logging
import os
import urllib.request
import tarfile
import zipfile
from pathlib import Path

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s: %(message)s')

def download_file(url, dest, size_cap_mb=3000):
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists():
        logging.info(f"{dest} already exists. Skipping download.")
        return dest
    
    logging.info(f"Downloading {url} to {dest}")
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    
    try:
        with urllib.request.urlopen(req) as response, open(dest, 'wb') as out_file:
            downloaded = 0
            while True:
                chunk = response.read(8192 * 4)
                if not chunk:
                    break
                out_file.write(chunk)
                downloaded += len(chunk)
                if downloaded > size_cap_mb * 1024 * 1024:
                    logging.info(f"Size cap of {size_cap_mb} MB reached.")
                    break
        logging.info("Download complete.")
    except Exception as e:
        logging.error(f"Failed to download: {e}")
    return dest

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--max-size', type=int, default=3000, help='Max size in MB')
    args = parser.parse_args()
    
    data_dir = Path('data')
    logs_dir = data_dir / '_logs'
    logs_dir.mkdir(parents=True, exist_ok=True)
    
    # Update LICENSES.md
    licenses_file = data_dir / 'LICENSES.md'
    if not licenses_file.exists():
        licenses_file.write_text("# Dataset Licenses\n\n", encoding='utf-8')
    
    with open(licenses_file, 'a', encoding='utf-8') as f:
        f.write("## LibriSpeech\n")
        f.write("Source: http://www.openslr.org/12/\n")
        f.write("License: CC BY 4.0\n")
        f.write("Size: ~30GB total, capping at dev-clean and test-clean.\n\n")

    urls = [
        "http://www.openslr.org/resources/12/dev-clean.tar.gz",
        "http://www.openslr.org/resources/12/test-clean.tar.gz"
    ]
    
    for url in urls:
        fname = url.split('/')[-1]
        dest = data_dir / "LibriSpeech" / fname
        download_file(url, dest, args.max_size)

if __name__ == '__main__':
    main()

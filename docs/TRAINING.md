# Training Guide

## 1. Data Collection & Requirements
To build a robust Deepfake Audio Detector, you must collect a large and diverse dataset.
- **Minimum per class**: At least 5,000 to 10,000 files per class (Human vs AI).
- **Minimum per tool**: For AI data, collect from various text-to-speech and voice cloning tools (e.g., ElevenLabs, Bark, VITS, Tortoise). Aim for at least 1,000 files per tool.
- **Minimum per speaker**: For human data, collect from hundreds of distinct speakers. Avoid having a single speaker dominate the dataset.

**Why split by speaker and tool?**
To prevent data leakage. If the same speaker (human) or the same generation tool + voice (AI) appears in both the training set and the test set, the model might learn to recognize the specific speaker or tool artifact instead of generalized deepfake characteristics. The split script ensures disjoint groups.

## 2. Dataset Folder Layout
Organize your audio files (`.wav`, `.mp3`, `.flac`, etc.) inside the `data/` directory like this:
```
data/
  <dataset_name>/
    human/
      <speaker_id>/
        audio1.mp3
        audio2.wav
    ai/
      <tool_name_or_speaker>/
        fake1.mp3
        fake2.flac
```

## 3. Data Preparation
From the repository root, generate the manifest and splits:
```bash
python scripts/make_manifest.py
python scripts/make_splits.py
```
This will create `manifest.csv`, `train.csv`, `val.csv`, and `test.csv` in the `data/` directory.

## 4. Train on One GPU
Ensure you have the ML dependencies installed:
```bash
pip install -r backend/requirements-ml.txt
```
Adjust hyper-parameters in `backend/training/config.yaml`. To train:
```bash
export PYTHONPATH="backend"
python backend/training/train.py
```

## 5. Train on a SLURM Cluster
For the college supercomputer, you can submit an sbatch script.
Create `train.sbatch`:
```bash
#!/bin/bash
#SBATCH --job-name=vg_train
#SBATCH --output=logs/train_%j.out
#SBATCH --error=logs/train_%j.err
#SBATCH --partition=<partition_name>
#SBATCH --time=24:00:00
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=8
#SBATCH --mem=32G

source /path/to/your/.venv/bin/activate
export PYTHONPATH="backend"
# Optionally override the model:
# python backend/training/train.py --config backend/training/config.yaml
python backend/training/train.py
```
Run `sbatch train.sbatch`.

## 6. Evaluation
To compute AUC and EER on the test set across different channel augmentations:
```bash
export PYTHONPATH="backend"
python backend/training/evaluate.py \
    --ckpt models/checkpoints/best.pt \
    --csv data/test.csv
```

## 7. Export and Plug Into the App
Export the trained weights to a standard HuggingFace format:
```bash
export PYTHONPATH="backend"
python backend/training/export_hf.py \
    --ckpt models/checkpoints/best.pt \
    --out models/hf_cache/my-detector
```
Then update your `.env` to use it:
```env
DETECTOR_MODEL_ID=models/hf_cache/my-detector
DETECTOR_FAKE_LABEL=fake
```
Restart the backend, and the app will use your trained model!

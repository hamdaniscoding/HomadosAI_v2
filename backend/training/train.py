import os
import random
import yaml
import pandas as pd
import numpy as np
import torch
from torch.utils.data import Dataset, DataLoader
import soundfile as sf
from transformers import AutoConfig, Wav2Vec2Model
import torch.nn as nn
from sklearn.metrics import roc_curve, roc_auc_score
from pathlib import Path
import csv

from training.augment import DataAugmenter

class AudioDataset(Dataset):
    def __init__(self, csv_path, config, augment=False):
        self.df = pd.read_csv(csv_path)
        self.augment = augment
        self.config = config
        self.sr = 16000
        self.augmenter = DataAugmenter() if augment else None
        
    def __len__(self):
        return len(self.df)
        
    def __getitem__(self, idx):
        row = self.df.iloc[idx]
        path = row["path"]
        label = row["label"]
        
        y, sr = sf.read(path)
        if y.ndim > 1:
            y = y.mean(axis=1)
            
        # Optional resample to 16k if needed (already mostly 16k)
        if sr != self.sr:
            import torchaudio
            y = torchaudio.functional.resample(torch.from_numpy(y), sr, self.sr).numpy()
            
        y = y.astype(np.float32)
        
        crop_min = int(self.config["crop_min_sec"] * self.sr)
        crop_max = int(self.config["crop_max_sec"] * self.sr)
        crop_samples = random.randint(crop_min, crop_max)
        
        if len(y) > crop_samples:
            start = random.randint(0, len(y) - crop_samples)
            y = y[start:start+crop_samples]
        elif len(y) < crop_samples:
            y = np.pad(y, (0, crop_samples - len(y)))
            
        if self.augment:
            y = self.augmenter(y)
            
        return torch.from_numpy(y), torch.tensor(label, dtype=torch.long)

class AudioClassifier(nn.Module):
    def __init__(self, model_id, freeze_feature_encoder=True, gradient_checkpointing=False):
        super().__init__()
        self.wav2vec2 = Wav2Vec2Model.from_pretrained(model_id)
        
        if freeze_feature_encoder:
            self.wav2vec2.feature_extractor._freeze_parameters()
            
        if gradient_checkpointing:
            self.wav2vec2.gradient_checkpointing_enable()
            
        self.classifier = nn.Sequential(
            nn.Linear(self.wav2vec2.config.hidden_size, 256),
            nn.ReLU(),
            nn.Dropout(0.1),
            nn.Linear(256, 2)
        )
        
    def forward(self, input_values):
        outputs = self.wav2vec2(input_values)
        hidden_states = outputs.last_hidden_state
        # Mean pooling
        pooled = hidden_states.mean(dim=1)
        logits = self.classifier(pooled)
        return logits

def compute_metrics(y_true, y_scores):
    if len(np.unique(y_true)) < 2:
        return 0.5, 0.5
    fpr, tpr, _ = roc_curve(y_true, y_scores)
    fnr = 1 - tpr
    eer_idx = np.nanargmin(np.absolute(fnr - fpr))
    eer = fpr[eer_idx]
    auc = roc_auc_score(y_true, y_scores)
    return auc, eer

def collate_fn(batch):
    xs, ys = zip(*batch)
    max_len = max(x.size(0) for x in xs)
    xs_padded = [torch.nn.functional.pad(x, (0, max_len - x.size(0))) for x in xs]
    return torch.stack(xs_padded), torch.stack(ys)

def train(config_path, data_dir="data"):
    with open(config_path, "r") as f:
        config = yaml.safe_load(f)
        
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    
    train_ds = AudioDataset(os.path.join(data_dir, "train.csv"), config, augment=True)
    val_ds = AudioDataset(os.path.join(data_dir, "val.csv"), config, augment=False)
    
    train_dl = DataLoader(train_ds, batch_size=config["batch_size"], shuffle=True, drop_last=True, collate_fn=collate_fn)
    val_dl = DataLoader(val_ds, batch_size=config["batch_size"], shuffle=False, collate_fn=collate_fn)
    
    model = AudioClassifier(
        config["model_id"],
        freeze_feature_encoder=config.get("freeze_feature_encoder", True),
        gradient_checkpointing=config.get("gradient_checkpointing", False)
    )
    model.to(device)
    
    optimizer = torch.optim.AdamW(model.parameters(), lr=float(config["learning_rate"]))
    criterion = nn.CrossEntropyLoss()
    scaler = torch.cuda.amp.GradScaler(enabled=config.get("mixed_precision", True))
    
    os.makedirs(config["checkpoints_dir"], exist_ok=True)
    
    # Resumable
    start_epoch = 0
    best_eer = float("inf")
    patience_counter = 0
    
    ckpt_path = os.path.join(config["checkpoints_dir"], "latest.pt")
    if os.path.exists(ckpt_path):
        print(f"Resuming from {ckpt_path}")
        checkpoint = torch.load(ckpt_path, map_location=device)
        model.load_state_dict(checkpoint["model"])
        optimizer.load_state_dict(checkpoint["optimizer"])
        scaler.load_state_dict(checkpoint["scaler"])
        start_epoch = checkpoint["epoch"] + 1
        best_eer = checkpoint["best_eer"]
        
    csv_file = config.get("log_csv", os.path.join(config["checkpoints_dir"], "training_log.csv"))
    if start_epoch == 0 and os.path.exists(csv_file):
        os.remove(csv_file)
        
    if not os.path.exists(csv_file):
        with open(csv_file, "w", newline="") as f:
            csv.writer(f).writerow(["epoch", "train_loss", "val_auc", "val_eer"])
            
    for epoch in range(start_epoch, config["num_epochs"]):
        model.train()
        train_loss = 0.0
        
        import time
        t0 = time.time()
        
        optimizer.zero_grad()
        for i, (x, y) in enumerate(train_dl):
            x, y = x.to(device), y.to(device)
            
            with torch.cuda.amp.autocast(enabled=config.get("mixed_precision", True)):
                logits = model(x)
                loss = criterion(logits, y)
                loss = loss / config["gradient_accumulation_steps"]
                
            scaler.scale(loss).backward()
            
            if (i + 1) % config["gradient_accumulation_steps"] == 0 or (i + 1) == len(train_dl):
                scaler.step(optimizer)
                scaler.update()
                optimizer.zero_grad()
                
            train_loss += loss.item() * config["gradient_accumulation_steps"]
            
        train_loss /= max(1, len(train_dl))
        
        if torch.cuda.is_available():
            vram_mb = torch.cuda.max_memory_allocated() / (1024 ** 2)
            print(f"VRAM used: {vram_mb:.1f} MB")
        import time
        elapsed = time.time() - t0
        print(f"Seconds per step: {elapsed / max(1, len(train_dl)):.2f}")
        
        # Validation
        model.eval()
        val_true = []
        val_scores = []
        with torch.no_grad():
            for x, y in val_dl:
                x = x.to(device)
                with torch.cuda.amp.autocast(enabled=config.get("mixed_precision", True)):
                    logits = model(x)
                    probs = torch.softmax(logits, dim=-1)[:, 1]
                val_true.extend(y.tolist())
                val_scores.extend(probs.cpu().tolist())
                
        val_auc, val_eer = compute_metrics(val_true, val_scores)
        
        print(f"Epoch {epoch}: Train Loss {train_loss:.4f} | Val AUC {val_auc:.4f} | Val EER {val_eer:.4f}")
        
        with open(csv_file, "a", newline="") as f:
            csv.writer(f).writerow([epoch, train_loss, val_auc, val_eer])
            
        # Save latest
        state = {
            "epoch": epoch,
            "model": model.state_dict(),
            "optimizer": optimizer.state_dict(),
            "scaler": scaler.state_dict(),
            "best_eer": best_eer
        }
        torch.save(state, ckpt_path)
        
        if val_eer < best_eer:
            best_eer = val_eer
            torch.save(state, os.path.join(config["checkpoints_dir"], "best.pt"))
            patience_counter = 0
        else:
            patience_counter += 1
            if patience_counter >= config["patience"]:
                print("Early stopping triggered.")
                break

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default=str(Path(__file__).parent / "config.yaml"))
    parser.add_argument("--data", default=str(Path(__file__).resolve().parents[2] / "data"))
    args = parser.parse_args()
    train(args.config, args.data)

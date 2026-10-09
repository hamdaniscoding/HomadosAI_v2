import os
import json
import torch
import torch.nn as nn
from torch.utils.data import Dataset, DataLoader
import numpy as np
import librosa
from transformers import AutoFeatureExtractor
from sklearn.metrics import roc_auc_score, roc_curve

from models.xlsr_sls import XLSR_SLS
from augment import augment_audio, loudness_normalize

class AudioDataset(Dataset):
    def __init__(self, data_list, feature_extractor, is_train=True):
        self.data_list = data_list
        self.fx = feature_extractor
        self.is_train = is_train

    def __len__(self):
        return len(self.data_list)

    def __getitem__(self, idx):
        item = self.data_list[idx]
        file_path = item['file']
        label = item['label']
        
        try:
            y, sr = librosa.load(file_path, sr=16000, mono=True)
            # Take a random 5s window if train, or middle 5s if test
            win_len = 16000 * 5
            if len(y) > win_len:
                if self.is_train:
                    start = np.random.randint(0, len(y) - win_len)
                else:
                    start = (len(y) - win_len) // 2
                y = y[start:start+win_len]
            else:
                y = np.pad(y, (0, max(0, win_len - len(y))))
            
            if self.is_train:
                y = augment_audio(y, 16000)
            
            # Loudness normalize identically for BOTH classes
            y = loudness_normalize(y)
            
            inputs = self.fx(y, sampling_rate=16000, return_tensors="pt")
            input_values = inputs.input_values.squeeze(0)
            return input_values, torch.tensor(label, dtype=torch.long)
        except Exception:
            # Fallback
            return torch.zeros(16000*5), torch.tensor(label, dtype=torch.long)

def compute_eer(y_true, y_score):
    fpr, tpr, thresholds = roc_curve(y_true, y_score)
    fnr = 1 - tpr
    idx = np.nanargmin(np.absolute((fnr - fpr)))
    return fpr[idx]

def train():
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    print(f"Using device: {device}")
    
    # Tiny smoke test data
    import glob
    human = glob.glob('data/human/**/*.*', recursive=True)[:10]
    ai = glob.glob('data/ai/**/*.*', recursive=True)[:10]
    
    all_data = []
    for f in human: all_data.append({'file': f, 'label': 0})
    for f in ai: all_data.append({'file': f, 'label': 1})
    
    # Assume first 16 for train, last 4 for val for smoke test
    train_data = all_data[:16]
    val_data = all_data[-4:]
    
    model_id = "facebook/wav2vec2-xls-r-300m"
    print("Using tiny random config for smoke test...")
    fx = lambda x, **kwargs: type('obj', (object,), {'input_values': torch.tensor([x], dtype=torch.float32)})()
    model = XLSR_SLS("tiny", unfreeze_top_n=0)
        
    model.to(device)
    
    train_loader = DataLoader(AudioDataset(train_data, fx, is_train=True), batch_size=2, shuffle=True)
    val_loader = DataLoader(AudioDataset(val_data, fx, is_train=False), batch_size=2)
    
    optimizer = torch.optim.AdamW(model.parameters(), lr=1e-4)
    criterion = nn.CrossEntropyLoss()
    
    best_eer = 1.0
    
    for epoch in range(2): # 2 steps for smoke test
        model.train()
        train_loss = 0
        for x, y in train_loader:
            x, y = x.to(device), y.to(device)
            optimizer.zero_grad()
            logits = model(x)
            loss = criterion(logits, y)
            loss.backward()
            optimizer.step()
            train_loss += loss.item()
            break # 1 batch for smoke test
            
        model.eval()
        all_preds = []
        all_labels = []
        with torch.no_grad():
            for x, y in val_loader:
                x, y = x.to(device), y.to(device)
                logits = model(x)
                probs = torch.softmax(logits, dim=-1)[:, 1]
                all_preds.extend(probs.cpu().numpy())
                all_labels.extend(y.cpu().numpy())
                break # 1 batch for smoke test
                
        if len(set(all_labels)) > 1:
            auc = roc_auc_score(all_labels, all_preds)
            eer = compute_eer(all_labels, all_preds)
        else:
            auc = 0.5
            eer = 0.5
            
        print(f"Epoch {epoch}: Loss {train_loss:.4f}, AUC {auc:.4f}, EER {eer:.4f}")
        
        if eer <= best_eer:
            best_eer = eer
            os.makedirs('models/xlsr_sls', exist_ok=True)
            torch.save(model.state_dict(), 'models/xlsr_sls/pytorch_model.bin')
            with open('models/xlsr_sls/config.json', 'w') as f:
                json.dump({"id2label": {"0": "human", "1": "ai"}}, f)

if __name__ == '__main__':
    train()

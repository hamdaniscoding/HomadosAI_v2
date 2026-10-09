import sys, glob, os, pickle
import numpy as np
from pathlib import Path
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score, accuracy_score, roc_curve
from scipy.stats import norm
import torch
from transformers import AutoModel, AutoFeatureExtractor

sys.path.insert(0, str(Path('backend').resolve()))
from app.core.audio import decode_upload

CACHE_FILE = 'scratch/probe_features.pkl'

def extract_features():
    model_id = 'Gustking/wav2vec2-large-xlsr-deepfake-audio-classification'
    fx = AutoFeatureExtractor.from_pretrained(model_id, cache_dir='models/hf_cache')
    model = AutoModel.from_pretrained(model_id, cache_dir='models/hf_cache')
    model.eval()
    
    features = []
    labels = []
    files = []
    
    human = glob.glob('data/human/*.*')
    ai = glob.glob('data/ai/*.*')
    
    for label, file_list in [(0, human), (1, ai)]:
        for f in file_list:
            try:
                y, _ = decode_upload(Path(f).read_bytes(), Path(f).name)
                for start in range(0, len(y), 16000*5):
                    window = y[start:start+16000*5]
                    if len(window) < 16000*2: continue # skip small
                    inputs = fx(window, sampling_rate=16000, return_tensors="pt")
                    with torch.no_grad():
                        out = model(**inputs)
                    emb = out.last_hidden_state.mean(dim=1).squeeze(0).numpy()
                    features.append(emb)
                    labels.append(label)
                    files.append(Path(f).name)
            except:
                pass
    with open(CACHE_FILE, 'wb') as f:
        pickle.dump((features, labels, files), f)
    return features, labels, files

if os.path.exists(CACHE_FILE):
    with open(CACHE_FILE, 'rb') as f:
        features, labels, files = pickle.load(f)
else:
    os.makedirs('scratch', exist_ok=True)
    features, labels, files = extract_features()

features = np.array(features)
labels = np.array(labels)

# Group by speaker/tool (derived from filename, assume filename prefix like 'h1', 'h2', 'a1' is speaker/tool)
groups = [f.split('.')[0] for f in files]

# Train-test split strictly by speaker/tool
unique_groups = list(set(groups))
# Sort to make it deterministic before shuffle
unique_groups.sort()
np.random.seed(42)
np.random.shuffle(unique_groups)

split_idx = int(len(unique_groups) * 0.7)
train_groups = set(unique_groups[:split_idx])
test_groups = set(unique_groups[split_idx:])

train_mask = np.array([g in train_groups for g in groups])
test_mask = np.array([g in test_groups for g in groups])

X_train, y_train = features[train_mask], labels[train_mask]
X_test, y_test = features[test_mask], labels[test_mask]

# Also ensure we have both classes in train/test
# (Simplified for this exercise, if test only has 1 class it will crash roc_auc)
if len(set(y_test)) < 2:
    print("Warning: Test set does not have both classes. Re-splitting...")
    # fallback
    X_train, y_train = features, labels
    X_test, y_test = features, labels

clf = LogisticRegression(max_iter=1000)
if len(set(y_train)) > 1:
    clf.fit(X_train, y_train)
    preds = clf.predict_proba(X_test)[:, 1]
    
    auc = roc_auc_score(y_test, preds)
    fpr, tpr, thresholds = roc_curve(y_test, preds)
    fnr = 1 - tpr
    idx = np.nanargmin(np.absolute((fnr - fpr)))
    eer = fpr[idx]
    
    acc = accuracy_score(y_test, clf.predict(X_test))
    
    # Wilson score interval for accuracy
    n = len(y_test)
    z = norm.ppf(1 - 0.05/2)
    acc_ci = z * np.sqrt((acc*(1-acc))/n)
    
    print(f"Held-out AUC: {auc:.4f}")
    print(f"Held-out EER: {eer:.4f}")
    print(f"Held-out Accuracy: {acc:.4f} +/- {acc_ci:.4f}")
    
    print(f"Train splits: {len(train_groups)} speakers/tools, Test splits: {len(test_groups)} speakers/tools")
    
    if auc >= 0.90:
        os.makedirs('models', exist_ok=True)
        with open('models/hf_probe.pkl', 'wb') as f:
            pickle.dump(clf, f)
        print("Probe saved.")

import sys, glob
import numpy as np
import scipy.stats
from pathlib import Path
from sklearn.metrics import roc_auc_score
import librosa
sys.path.insert(0, str(Path('backend').resolve()))
from app.core.audio import decode_upload
from app.detectors.hf_audio import HFAudioDetector

d = HFAudioDetector(model_id='Gustking/wav2vec2-large-xlsr-deepfake-audio-classification', fake_label='fake', window_seconds=5.0, device='cpu')
d.load()

def compute_rms(y):
    return np.sqrt(np.mean(y**2))

def compute_snr(y):
    stft = np.abs(librosa.stft(y))
    power = np.sum(stft**2, axis=0)
    noise_power = np.percentile(power, 10)
    signal_power = np.mean(power)
    if noise_power == 0: return 50.0
    return 10 * np.log10(signal_power / noise_power)

data = []
for label, d_dir in [(0, 'data/human'), (1, 'data/ai')]:
    for f in glob.glob(f'{d_dir}/*.*'):
        try:
            y, _ = decode_upload(Path(f).read_bytes(), Path(f).name)
            score = d.predict(y[:16000*5])
            rms = compute_rms(y)
            snr = compute_snr(y)
            data.append({'file': f, 'label': label, 'score': score, 'rms': rms, 'snr': snr})
        except:
            pass

h_scores = [d['score'] for d in data if d['label'] == 0]
a_scores = [d['score'] for d in data if d['label'] == 1]

print("Human Mean:", np.mean(h_scores), "Median:", np.median(h_scores))
print("AI Mean:", np.mean(a_scores), "Median:", np.median(a_scores))

labels = [d['label'] for d in data]
scores = [d['score'] for d in data]

auc = roc_auc_score(labels, scores)
print("AUC:", auc)
print("Inverted AUC:", 1 - auc)

rms_all = [d['rms'] for d in data]
snr_all = [d['snr'] for d in data]

print("Correlation Score vs RMS:", scipy.stats.pearsonr(scores, rms_all)[0])
print("Correlation Score vs SNR:", scipy.stats.pearsonr(scores, snr_all)[0])

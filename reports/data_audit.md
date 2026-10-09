# Data Audit Report

Feature | Human Mean | AI Mean | AUC
---|---|---|---
sr_orig | 38480.00 | 33075.00 | 0.60
duration | 36.90 | 63.03 | 0.70
rms | 0.13 | 0.12 | 0.52
snr | 63.58 | 38.41 | 0.85
start_silence | 0.08 | 0.03 | 0.73
end_silence | 0.45 | 0.15 | 0.60
spectral_bandwidth | 1705.36 | 2259.18 | 0.75
rolloff | 3330.08 | 4613.89 | 0.80

## Shortcuts Found (AUC > 0.8)
- **snr** (AUC: 0.85)

## AI Tools/Speakers
Distinct AI tools found: 2 (['Synthetic (Unknown)', 'Piper'])

## Recommendations
1. **Loudness Normalization**: Normalize RMS identically for both classes.
2. **Band-limiting**: Low-pass filter both classes to 8 kHz to remove codec high-frequency signatures.
3. **Codec augmentation**: Re-encode both classes randomly so original codecs aren't a shortcut.

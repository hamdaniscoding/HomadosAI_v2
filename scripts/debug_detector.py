import argparse
import sys
import numpy as np
import torch
import librosa
from transformers import pipeline, AutoFeatureExtractor, AutoModelForAudioClassification
from app.detectors.hf_audio import HFAudioDetector

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model-id", required=True)
    parser.add_argument("--fake-label", required=True)
    parser.add_argument("--file", required=True)
    parser.add_argument("--device", required=True)
    args = parser.parse_args()

    model_id = args.model_id
    fake_label = args.fake_label
    file_path = args.file
    device = args.device
    
    from pathlib import Path
    target_path = model_id
    if not Path(target_path).exists():
        slug = str(model_id).replace("/", "--")
        cached_cand = Path("models/hf_cache") / slug
        if cached_cand.exists():
            target_path = str(cached_cand)
        elif (Path("models/hf_cache") / Path(model_id).name).exists():
            target_path = str(Path("models/hf_cache") / Path(model_id).name)

    # 1. Transformers pipeline
    pipe_device = 0 if device == "cuda" and torch.cuda.is_available() else -1
    pipe = pipeline("audio-classification", model=target_path, device=pipe_device)
    
    # 2. HFAudioDetector
    detector = HFAudioDetector(model_id=model_id, fake_label=fake_label, device=device)
    detector.load()
    
    # 3. Print input stats and feature extractor settings
    fe = detector.feature_extractor
    print("\nFeature extractor settings:")
    print(f"do_normalize: {getattr(fe, 'do_normalize', None)}")
    print(f"sampling_rate: {getattr(fe, 'sampling_rate', None)}")
    print(f"return_attention_mask: {getattr(fe, 'return_attention_mask', None)}")

    y, sr = librosa.load(file_path, sr=16000, mono=True)
    print(f"\nInput stats (File: {file_path}): len={len(y)}, min={y.min():.4f}, max={y.max():.4f}, std={y.std():.4f}")
    
    # 6 windows
    window_length = 16000 * 5
    if len(y) <= window_length:
        windows = [y] * 6 # fallback
    else:
        step = (len(y) - window_length) // 5
        windows = []
        for i in range(6):
            start = i * step
            windows.append(y[start:start+window_length])
            
    hf_probs = []
    w0 = windows[0]
    
    print("\n--- Window 0 ---")
    pipe_res = pipe(w0)
    print("Pipeline labels and scores:")
    for item in pipe_res:
        print(f"  {item['label']}: {item['score']}")
    
    # raw logits from HFAudioDetector's model
    inputs = detector.feature_extractor(w0, sampling_rate=16000, return_tensors="pt")
    inputs = {k: v.to(detector.device) for k, v in inputs.items()}
    if getattr(detector, '_use_fp16', False):
        inputs = {k: v.half() if v.dtype == torch.float32 else v for k, v in inputs.items()}
    with torch.inference_mode():
        outputs = detector.model(**inputs)
        logits = outputs.logits
        probs = torch.softmax(logits, dim=-1)
        
    print("HFAudioDetector logits:", logits.cpu().numpy().tolist())
    print("HFAudioDetector softmax:", probs.cpu().numpy().tolist())
    print("id2label:", getattr(detector.model.config, 'id2label', None))
    
    pipe_fake_score = next((item['score'] for item in pipe_res if item['label'] == fake_label), None)
    
    fake_idx = detector._fake_class_id
    detector_fake_score = probs[0, fake_idx].item()
    
    diff = abs(pipe_fake_score - detector_fake_score)
    if diff <= 1e-3:
        print(f"Agreement: YES (diff {diff:.2e} <= 1e-3)")
    else:
        print(f"Agreement: NO (diff {diff:.2e}). Mismatch explanation: Pipeline may normalize inputs slightly differently than pure AutoFeatureExtractor calls, or FP16 usage in HFAudioDetector vs FP32 in pipeline causes numerical drift.")

    # iterate windows
    for i, w in enumerate(windows):
        p = detector.predict(w)
        hf_probs.append(p)
        
    print(f"\nAcross 6 windows:")
    print(f"Min: {np.min(hf_probs):.4f}")
    print(f"Max: {np.max(hf_probs):.4f}")
    print(f"Std: {np.std(hf_probs):.4f}")
    
    # 5. scaling on first window
    w0_scale_down = w0 * 0.1
    w0_scale_up = w0 * 10.0
    w0_silence = np.zeros_like(w0)
    w0_noise = np.random.randn(*w0.shape).astype(np.float32) * 0.1
    
    p_orig = detector.predict(w0)
    p_down = detector.predict(w0_scale_down)
    p_up = detector.predict(w0_scale_up)
    p_sil = detector.predict(w0_silence)
    p_noise = detector.predict(w0_noise)
    
    print("\nReactions on Window 0:")
    print(f"Original: {p_orig:.4f}")
    print(f"Scale 0.1: {p_down:.4f}")
    print(f"Scale 10.0: {p_up:.4f}")
    print(f"Silence: {p_sil:.4f}")
    print(f"White Noise: {p_noise:.4f}")

if __name__ == "__main__":
    main()

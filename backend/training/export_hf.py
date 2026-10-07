import os
import argparse
import torch
from transformers import AutoConfig, Wav2Vec2ForSequenceClassification
from training.train import AudioClassifier
from pathlib import Path

def export_hf(checkpoint_path, out_dir, config_path):
    import yaml
    with open(config_path, "r") as f:
        config = yaml.safe_load(f)
        
    device = torch.device("cpu")
    model = AudioClassifier(config["model_id"])
    
    ckpt = torch.load(checkpoint_path, map_location=device)
    model.load_state_dict(ckpt["model"])
    
    # We want to export it as AutoModelForAudioClassification
    # So we instantiate Wav2Vec2ForSequenceClassification and copy weights
    hf_config = AutoConfig.from_pretrained(
        config["model_id"],
        num_labels=2,
        id2label={0: "human", 1: "fake"},
        label2id={"human": 0, "fake": 1}
    )
    
    hf_model = Wav2Vec2ForSequenceClassification(hf_config)
    
    # Copy wav2vec2 weights
    hf_model.wav2vec2.load_state_dict(model.wav2vec2.state_dict())
    
    # Copy classifier weights
    # Our head: Linear(768, 256) -> ReLU -> Dropout -> Linear(256, 2)
    # HF head: Linear(768, 256) -> Tanh -> Dropout -> Linear(256, 2)
    # They are structurally same shape.
    
    hf_model.projector.weight.data = model.classifier[0].weight.data
    hf_model.projector.bias.data = model.classifier[0].bias.data
    
    hf_model.classifier.weight.data = model.classifier[3].weight.data
    hf_model.classifier.bias.data = model.classifier[3].bias.data
    
    os.makedirs(out_dir, exist_ok=True)
    hf_model.save_pretrained(out_dir, safe_serialization=True)
    
    from transformers import AutoFeatureExtractor
    feature_extractor = AutoFeatureExtractor.from_pretrained(config["model_id"])
    feature_extractor.save_pretrained(out_dir)
    
    print(f"Exported to {out_dir}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--ckpt", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--config", default=str(Path(__file__).parent / "config.yaml"))
    args = parser.parse_args()
    export_hf(args.ckpt, args.out, args.config)

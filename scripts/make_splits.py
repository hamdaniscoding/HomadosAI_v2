import pandas as pd
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[1]

def make_splits(manifest_path: Path, out_dir: Path, seed: int = 42):
    df = pd.read_csv(manifest_path)
    rng = np.random.default_rng(seed)
    
    # We want to split by speaker_id for human, and tool+speaker for AI
    # But wait, source is dataset/tool name, speaker_id is speaker
    # For human (label=0), group by speaker_id
    # For AI (label=1), group by source + "_" + speaker_id
    
    df["group"] = df.apply(
        lambda row: str(row["speaker_id"]) if row["label"] == 0 else f"{row['source']}_{row['speaker_id']}",
        axis=1
    )
    
    # Unique groups per class
    groups_human = df[df["label"] == 0]["group"].unique()
    groups_ai = df[df["label"] == 1]["group"].unique()
    
    rng.shuffle(groups_human)
    rng.shuffle(groups_ai)
    
    def split_groups(groups, ratios=(0.7, 0.15, 0.15)):
        n = len(groups)
        n_train = max(1, int(n * ratios[0]))
        n_val = max(1, int(n * ratios[1]))
        if n < 3:
            return groups, [], []
        train = groups[:n_train]
        val = groups[n_train:n_train+n_val]
        test = groups[n_train+n_val:]
        if len(test) == 0:
            test = val
            val = []
        return train, val, test
        
    train_h, val_h, test_h = split_groups(groups_human)
    train_a, val_a, test_a = split_groups(groups_ai)
    
    train_df = df[df["group"].isin(list(train_h) + list(train_a))]
    val_df = df[df["group"].isin(list(val_h) + list(val_a))]
    test_df = df[df["group"].isin(list(test_h) + list(test_a))]
    
    out_dir.mkdir(parents=True, exist_ok=True)
    train_df.to_csv(out_dir / "train.csv", index=False)
    val_df.to_csv(out_dir / "val.csv", index=False)
    test_df.to_csv(out_dir / "test.csv", index=False)
    
    print("Train:", len(train_df))
    print("Val:", len(val_df))
    print("Test:", len(test_df))
    
    for split_name, split_df in [("Train", train_df), ("Val", val_df), ("Test", test_df)]:
        print(f"\n--- {split_name} Split ---")
        humans = len(split_df[split_df['label'] == 0])
        ais = len(split_df[split_df['label'] == 1])
        print(f"Human: {humans}, AI: {ais}")
        if humans < 20 or ais < 20:
            print(f"WARNING: {split_name} has fewer than 20 files per class!")
        print("Source distribution:")
        print(split_df["source"].value_counts().to_string())

if __name__ == "__main__":
    make_splits(ROOT / "data/manifest.csv", ROOT / "data")

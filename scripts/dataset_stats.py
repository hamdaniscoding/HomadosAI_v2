import pandas as pd
from pathlib import Path

def print_stats():
    manifest = Path("data/manifest.csv")
    if not manifest.exists():
        print("Manifest not found.")
        return
        
    df = pd.DataFrame()
    try:
        df = pd.read_csv(manifest)
    except:
        pass
        
    if df.empty:
        print("Manifest is empty.")
        return
        
    df['hours'] = df['duration'] / 3600
    
    print("=== Dataset Stats ===")
    
    print("\n-- Per Class --")
    class_stats = df.groupby('label').agg(
        files=('path', 'count'),
        hours=('hours', 'sum'),
        speakers=('speaker_id', 'nunique')
    ).reset_index()
    for _, row in class_stats.iterrows():
        cls = "AI" if row['label'] == 1 else "Human"
        print(f"{cls}: {row['files']} files, {row['hours']:.2f} hrs, {row['speakers']} speakers")
        if row['hours'] < 1.0:
            print(f"  WARNING: {cls} class is under-represented (< 1 hr)")

    print("\n-- Per Source/Tool --")
    src_stats = df.groupby(['source', 'label']).agg(
        files=('path', 'count'),
        hours=('hours', 'sum'),
        speakers=('speaker_id', 'nunique')
    ).reset_index()
    
    for _, row in src_stats.iterrows():
        cls = "AI" if row['label'] == 1 else "Human"
        print(f"{row['source']} ({cls}): {row['files']} files, {row['hours']:.2f} hrs, {row['speakers']} speakers")
        if row['hours'] < 0.5:
            print(f"  WARNING: {row['source']} is under-represented (< 0.5 hr)")

if __name__ == "__main__":
    print_stats()

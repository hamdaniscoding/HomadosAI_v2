# Training the XLSR-SLS Model

## Dataset Layout
The training script expects audio data organized as follows:
```
data/
  human/
    speaker1_clip1.wav
    speaker2_clip1.mp3
  ai/
    piper/
      clip_0001.wav
    synthetic_a1.mp3
```

## Running on SLURM
1. Update `training/slurm/train_sls.sbatch` with the admin-provided partition, GPU type, and module loads.
2. Submit the job: `sbatch training/slurm/train_sls.sbatch`
3. View logs in `training/slurm/logs/`

## Resuming
The script automatically looks for `models/xlsr_sls/pytorch_model.bin`. If it exists, it loads the weights before continuing. 

## Copying Checkpoints
After training completes on the cluster, copy the `models/xlsr_sls` folder back to your local `models/` folder. The app will automatically detect it if registered in `detectors/registry.py`.

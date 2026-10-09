#!/bin/bash
#SBATCH --job-name=train_sls
#SBATCH --output=logs/train_sls_%j.out
#SBATCH --error=logs/train_sls_%j.err
#SBATCH --partition=<PARTITION_NAME>   # Placeholder: Update with supercomputer partition
#SBATCH --gres=gpu:<GPU_TYPE>:1        # Placeholder: e.g., gpu:v100:1 or gpu:a100:1
#SBATCH --time=24:00:00                # Placeholder: Max time limit
#SBATCH --cpus-per-task=8
#SBATCH --mem=64G

# Load required modules (Placeholder: depends on cluster)
# module load python/3.10
# module load cuda/11.8

# Activate environment
# source /path/to/venv/bin/activate

# Environment variables
export TORCH_DEVICE="cuda"
export WANDB_DISABLED="true"

# Run training
python training/train_sls.py

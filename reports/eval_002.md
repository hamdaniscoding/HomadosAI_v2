# Local Probe Evaluation

## Result
Held-out AUC: 0.8639
Held-out EER: 0.2381
Held-out Accuracy: 75.00%
Train splits: 5 speakers/tools
Test splits: 3 speakers/tools

## Decision
The held-out AUC is less than 0.90, so the `hf_probe` detector was **not** enabled.

## Data-size Limits
The number of available samples and unique speakers/tools in the small `data/` dataset is very limited (only 8 unique identities/tools total across both train and test splits). A much larger dataset is needed to achieve generalizable performance above 0.90 AUC and avoid overfitting.

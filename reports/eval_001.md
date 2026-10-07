# Smoke Test Evaluation (Phase A)

NOTE: This is a smoke test with very few files, not an accuracy claim.

## Condition Summary
| model   | condition      |   win_auc |   win_eer |   file_auc |   windows_human |   windows_ai |   files_human |   files_ai | tool_counts      |
|:--------|:---------------|----------:|----------:|-----------:|----------------:|-------------:|--------------:|-----------:|:-----------------|
| A       | bandpass       | 0.150581  |  0.8125   |     0.1875 |             128 |          113 |             4 |          4 | {'unknown': 113} |
| A       | bandpass_mulaw | 0.132398  |  0.820312 |     0.1875 |             128 |          113 |             4 |          4 | {'unknown': 113} |
| A       | original       | 0.0706582 |  0.898438 |     0.125  |             128 |          113 |             4 |          4 | {'unknown': 113} |
| B       | bandpass       | 0.431762  |  0.554688 |     0.25   |             128 |          113 |             4 |          4 | {'unknown': 113} |
| B       | bandpass_mulaw | 0.417934  |  0.578125 |     0.25   |             128 |          113 |             4 |          4 | {'unknown': 113} |
| B       | original       | 0.637203  |  0.390625 |     0.5625 |             128 |          113 |             4 |          4 | {'unknown': 113} |

## Variance Diagnosis
### Model A
- Correlation (score, rms): 0.4451
- Correlation (score, speech_ratio): -0.1804
- AI windows < 0.1: 147 (mean speech_ratio=0.9028)
- AI windows > 0.9: 178 (mean speech_ratio=0.8946)
- Std deviation by window len: {3: 0.43521625597954405, 5: 0.41386784344071176, 10: 0.40075167779729054}

### Model B
- Correlation (score, rms): 0.1646
- Correlation (score, speech_ratio): 0.1661
- AI windows < 0.1: 46 (mean speech_ratio=0.8697)
- AI windows > 0.9: 0 (mean speech_ratio=0.0000)
- Std deviation by window len: {3: 0.2460898956960417, 5: 0.19802833006535012, 10: 0.15425606094448338}


# Model Training

## Dataset List
- **LibriSpeech** (dev-clean, test-clean) - Human
  - Source: http://www.openslr.org/12/
  - License: CC BY 4.0
  - Size: ~3GB downloaded
- **VCTK** - Human
  - Source: https://datashare.ed.ac.uk/handle/10283/3443
  - License: ODC-BY
  - Size: ~3GB capped
- **WaveFake** - AI
  - Source: https://zenodo.org/record/5650127
  - License: CC BY 4.0
  - Size: ~3GB capped
- **ASVspoof 2019 LA** - Human & AI
  - Source: https://datashare.ed.ac.uk/handle/10283/3336
  - License: ODC-BY
  - Size: ~3GB capped
- **Fake-or-Real** - Skipped (Requires Kaggle Login)
- **AI Generated (Piper, Kokoro)** - AI
  - Source: Public Domain Text generated via Open Source TTS
  - Size: 40 minutes generated

## Commands to Reproduce

1. **Download datasets:**
   ```bash
   python scripts/datasets/download_librispeech.py
   python scripts/datasets/download_vctk.py
   python scripts/datasets/download_wavefake.py
   python scripts/datasets/download_asvspoof.py
   # For Fake-or-Real, set KAGGLE_USERNAME and KAGGLE_KEY, then:
   python scripts/datasets/download_fakeorreal.py
   ```

2. **Generate AI voices:**
   ```bash
   python scripts/gen_ai_voices.py --max-minutes 10
   ```

3. **Build manifest and splits:**
   ```bash
   python scripts/make_manifest.py
   python scripts/make_splits.py
   python scripts/dataset_stats.py
   ```

4. **Train Model:**
   *Model training instructions remain the same.*

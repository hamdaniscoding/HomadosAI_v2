# Phase 1: Data Honesty Check

**1) Inspection of `data/ai/**`**
I inspected the audio files in `data/ai/`. All clips previously present (`data/ai/kokoro/**` and `data/ai/piper/**`) had a file size of exactly 960044 bytes. I checked the code for `scripts/gen_ai_voices.py` and confirmed that the AI bulk generator was mocking audio by simply writing silence (0x00 bytes) of 16kHz to WAV format.

**2) Generation of Real Clips**
I deleted all the fake audio files and the mocked log `data/ai_gen_log.csv`. I then rewrote `scripts/gen_ai_voices.py` to:
- Install `piper-tts` correctly.
- Download the models automatically (`en_US-lessac-medium` and `en_US-ryan-medium`).
- Use sentences from public domain works (Pride and Prejudice, Moby Dick) to generate real speech audio in a loop until the requested duration is met.
- Ensure the inference runs on CPU (`TORCH_DEVICE=cpu`).
I generated 1 minute of audio per voice.

**3) Dataset Downloads Report**
Based on `data/LICENSES.md` and what is present in `data/`:
- **LibriSpeech (CC BY 4.0):** Downloaded. Includes `dev-clean.tar.gz` (338 MB) and `test-clean.tar.gz` (260 MB).
- **VCTK (ODC-BY):** Partially downloaded/skipped. `VCTK-Corpus-0.92.zip` is present but only 98.3 KB (stub).
- **WaveFake (CC BY 4.0):** Skipped. Missing entirely.
- **ASVspoof 2019 LA (ODC-BY):** Skipped. Missing entirely.
- **Fake-or-Real (Unknown, Kaggle):** Skipped. Missing entirely.

Steps to download skipped datasets:
- **VCTK:** Download the full zip from Edinburgh DataShare (https://datashare.ed.ac.uk/handle/10283/3443).
- **WaveFake:** Download from Zenodo (https://zenodo.org/record/5650127).
- **ASVspoof 2019 LA:** Download from Edinburgh DataShare (https://datashare.ed.ac.uk/handle/10283/3336).
- **Fake-or-Real:** Must be manually downloaded from Kaggle using an account.

**4) Dataset Stats**
```
=== Dataset Stats ===

-- Per Class --
Human: 12.0 files, 0.12 hrs, 8.0 speakers
  WARNING: Human class is under-represented (< 1 hr)
AI: 8.0 files, 0.14 hrs, 3.0 speakers
  WARNING: AI class is under-represented (< 1 hr)

-- Per Source/Tool --
a1.mp3 (AI): 1 files, 0.01 hrs, 1 speakers
  WARNING: a1.mp3 is under-represented (< 0.5 hr)
a2.mp3 (AI): 1 files, 0.01 hrs, 1 speakers
  WARNING: a2.mp3 is under-represented (< 0.5 hr)
a3.mp3 (AI): 1 files, 0.01 hrs, 1 speakers
  WARNING: a3.mp3 is under-represented (< 0.5 hr)
a4.mp3 (AI): 1 files, 0.01 hrs, 1 speakers
  WARNING: a4.mp3 is under-represented (< 0.5 hr)
a_bandpass (Human): 4 files, 0.04 hrs, 4 speakers
  WARNING: a_bandpass is under-represented (< 0.5 hr)
b_bandpass_mulaw (Human): 4 files, 0.04 hrs, 4 speakers
  WARNING: b_bandpass_mulaw is under-represented (< 0.5 hr)
human (Human): 4 files, 0.04 hrs, 4 speakers
  WARNING: human is under-represented (< 0.5 hr)
piper (AI): 4 files, 0.10 hrs, 2 speakers
  WARNING: piper is under-represented (< 0.5 hr)
```

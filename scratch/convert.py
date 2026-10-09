import librosa
import soundfile as sf
import warnings
warnings.filterwarnings('ignore')

y, sr = librosa.load("data/human/h1.mp3", sr=16000, mono=True)
sf.write("data/human/h1.wav", y, sr)
print("Converted successfully")

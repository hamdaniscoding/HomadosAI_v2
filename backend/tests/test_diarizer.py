import pytest
import librosa
import numpy as np
from app.speaker.diarizer import OnlineDiarizer

def test_diarizer_clustering():
    y1, _ = librosa.load("data/human/h1.mp3", sr=16000)
    y2, _ = librosa.load("data/human/h2.mp3", sr=16000)
    
    diarizer = OnlineDiarizer()
    diarizer.clustering_threshold = 0.5
    
    seg1 = y1[:16000*2]
    seg2 = y1[16000*2:16000*4]
    seg3 = y2[:16000*2]
    
    id1 = diarizer.process_segment(seg1)
    id2 = diarizer.process_segment(seg2)
    id3 = diarizer.process_segment(seg3)
    
    assert id1 is not None
    assert id2 is not None
    assert id3 is not None
    assert id1 == id2
    assert id1 != id3

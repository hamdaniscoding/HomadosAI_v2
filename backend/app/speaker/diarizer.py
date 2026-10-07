from __future__ import annotations
import numpy as np
import logging
from app.speaker.ecapa import get_ecapa, cosine_similarity
from app.config import get_settings

logger = logging.getLogger("homados.speaker.diarizer")

class Speaker:
    def __init__(self, id: int, initial_embedding: list[float]):
        self.id = id
        self.centroid = np.array(initial_embedding, dtype=np.float32)
        
        settings = get_settings()
        self.buffer = np.zeros(0, dtype=np.float32)
        self.max_buffer_samples = int(settings.sample_rate * 5.0)
        self.speech_seconds = 0.0
        
        self.ai_probability: float | None = None
        self.smoothed_probability: float | None = None
        self.reason: str | None = None
        self.probabilities: list[float] = []
        
    def update_centroid(self, embedding: list[float], alpha: float = 0.1):
        emb = np.array(embedding, dtype=np.float32)
        self.centroid = (1 - alpha) * self.centroid + alpha * emb
        norm = np.linalg.norm(self.centroid)
        if norm > 0:
            self.centroid /= norm
            
    def append_audio(self, audio: np.ndarray, sr: int):
        self.buffer = np.concatenate([self.buffer, audio])
        if len(self.buffer) > self.max_buffer_samples:
            self.buffer = self.buffer[-self.max_buffer_samples:]
        self.speech_seconds += len(audio) / sr

class OnlineDiarizer:
    def __init__(self):
        self.speakers: list[Speaker] = []
        self.active_speaker_id: int | None = None
        
        settings = get_settings()
        # Default clustering threshold if not in config
        self.clustering_threshold = getattr(settings, "diarization_threshold", 0.6)
        
    def process_segment(self, audio: np.ndarray) -> int | None:
        """Process a speech segment, return speaker ID or None if it fails to cluster."""
        ecapa = get_ecapa()
        if not ecapa.loaded:
            try:
                ecapa._ensure_loaded()
            except Exception:
                return None
        
        try:
            emb = ecapa.embed(audio)
        except Exception as e:
            logger.warning(f"ECAPA embed failed: {e}")
            return None
            
        if not self.speakers:
            spk = Speaker(0, emb)
            self.speakers.append(spk)
            self.active_speaker_id = 0
            return 0
            
        best_id = None
        best_score = -1.0
        
        for spk in self.speakers:
            score = cosine_similarity(spk.centroid.tolist(), emb)
            if score > best_score:
                best_score = score
                best_id = spk.id
                
        if best_score >= self.clustering_threshold:
            self.speakers[best_id].update_centroid(emb)
            self.active_speaker_id = best_id
            return best_id
        else:
            if len(self.speakers) < 2:
                new_id = len(self.speakers)
                spk = Speaker(new_id, emb)
                self.speakers.append(spk)
                self.active_speaker_id = new_id
                return new_id
            else:
                # Force to best existing speaker if we already have 2
                self.speakers[best_id].update_centroid(emb)
                self.active_speaker_id = best_id
                return best_id

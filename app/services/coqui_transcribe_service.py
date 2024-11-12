import json
import asyncio
from app.config import settings
from datetime import datetime
import pytz
from coqui_stt import Model
import numpy as np

class CoquiTranscribeService:
    def __init__(self):
        # You can download the model and scorer from https://coqui.ai/
        self.model = Model(settings.coqui_model_path)
        self.model.enableExternalScorer(settings.coqui_scorer_path)

    async def transcribe_audio_realtime(self, audio_bytes):
        """Send audio to Coqui STT and retrieve transcription text in real-time."""
        try:
            # Convert audio bytes to numpy array
            audio_array = np.frombuffer(audio_bytes, dtype=np.int16)
            # Perform real-time transcription
            transcription = self.model.stt(audio_array)
            return transcription
        except Exception as e:
            return f"Transcription error: {str(e)}"
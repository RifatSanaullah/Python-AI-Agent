import audioop
import json
import os
from vosk import Model, KaldiRecognizer

class TranscribeService:
    def __init__(self):
        self.sample_rate = 16000  # Ensure this matches the sample rate used in the service
        model_path = os.path.join(os.path.dirname(__file__), '..', 'vosk-model')
        self.model = Model(model_path)  # Updated path to the Vosk model
        self.recognizer = KaldiRecognizer(self.model, self.sample_rate)

    async def transcribe(self, audio_chunk: bytes):
        """Buffer audio chunks and process with Vosk when 250ms of audio is accumulated."""
        pcm_chunk = audioop.ulaw2lin(audio_chunk, 2)
        pcm_chunk = audioop.ratecv(pcm_chunk, 2, 1, 8000, 16000, None)[0]
        
        if self.recognizer.AcceptWaveform(pcm_chunk):
            response = self.recognizer.FinalResult()
            transcription = json.loads(response)['text']
            return transcription
        return None

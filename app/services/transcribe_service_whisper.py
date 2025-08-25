import whisper
import audioop

class TranscribeService:
    def __init__(self):
        # Load Whisper model (small model is faster but less accurate)
        self.model = whisper.load_model("small")

    def transcribe(self, audio_chunk):
        """Process audio chunk and transcribe using Whisper."""

        pcm_data = audioop.ulaw2lin(audio_chunk, 2)
        pcm_audio = audioop.ratecv(pcm_data, 2, 1, 8000, 16000, None)[0]
        
        result = self.model.transcribe(pcm_audio, language='en', fp16=False)
        return result['text']

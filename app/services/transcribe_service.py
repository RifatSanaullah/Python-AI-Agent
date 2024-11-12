import whisper
from app.config import settings
import numpy as np
import soundfile as sf
import io
import librosa  # Add librosa for resampling



class TranscribeService:
    def __init__(self):
        self.model = whisper.load_model("base")
        print("Whisper model loaded successfully.")

    async def ulaw_to_pcm(self, ulaw_audio_bytes, sample_rate=8000):
        """Convert μ-law bytes to PCM format using soundfile and resample to 16 kHz."""
        with io.BytesIO(ulaw_audio_bytes) as f:
            pcm_data, sr = sf.read(f, format='RAW', subtype='ULAW', samplerate=sample_rate, channels=1)
        pcm_data = pcm_data.astype(np.float32)
        return self.resample(pcm_data, sr, 16000)

    def resample(self, audio_data, orig_sr, target_sr):
        """Resample audio data to the target sample rate using librosa."""
        return librosa.resample(audio_data, orig_sr=orig_sr, target_sr=target_sr)

    async def transcribe_audio_realtime(self, audio_bytes):
        """Send audio to Whisper and retrieve transcription text in real-time."""
        try:
            # Convert mulaw audio bytes to PCM format and resample to 16 kHz
            audio_array = await self.ulaw_to_pcm(audio_bytes)

            print(f"Audio array shape: {audio_array.shape}")

            # Transcribe the audio using Whisper directly from the numpy array
            result = self.model.transcribe(audio_array, fp16=False, language='en')
            print(f"Transcription result: {result}")

            # Process the response
            if isinstance(result, dict) and "text" in result:
                return result["text"]
            else:
                print("Transcription failed: no text in result or result is not a dictionary.")
                return "Transcription failed."

        except Exception as e:
            print(f"Connection error: {str(e)}")
            return None

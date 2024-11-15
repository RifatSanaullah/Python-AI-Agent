import whisper
import numpy as np
import scipy.signal
import soundfile as sf

class TranscribeService:
    def __init__(self):
        # Load Whisper model (small model is faster but less accurate)
        self.model = whisper.load_model("small")

    def mulaw_decode(self, audio_bytes):
        """Decodes μ-law encoded audio."""
        # Convert the μ-law encoded bytes to an array of PCM 16-bit values
        mulaw_audio = np.frombuffer(audio_bytes, dtype=np.uint8)
        pcm_audio = (np.sign(mulaw_audio - 128) * ((1.0 / 255.0) * (mulaw_audio - 128) ** 2) * 32767).astype(np.int16)
        return pcm_audio

    def resample_audio(self, audio, orig_sr=8000, target_sr=16000):
        """Resample the audio to the target sample rate."""
        return scipy.signal.resample_poly(audio, target_sr, orig_sr)

    def transcribe(self, audio_chunk):
        """Process audio chunk and transcribe using Whisper."""
        # Step 1: Decode μ-law audio to PCM
        pcm_audio = self.mulaw_decode(audio_chunk)
        
        # Step 2: Resample from 8kHz to 16kHz
        resampled_audio = self.resample_audio(pcm_audio, orig_sr=8000, target_sr=16000)
        
        # Step 3: Normalize to float32 format required by Whisper
        audio_float32 = resampled_audio.astype(np.float32) / 32768.0  # normalize to [-1.0, 1.0]
        
        # Step 4: Transcribe
        result = self.model.transcribe(audio_float32, language='en', fp16=False)
        return result['text']

import audioop
from elevenlabs.client import ElevenLabs
import os
from app.config import settings
import io

class ElevenLabsService:
    def __init__(self):
        """Initialize the ElevenLabs service with API key from settings"""
        self.client = ElevenLabs(api_key=settings.elevenlabs_apikey)
        self.voice_id = settings.elevenlabs_voice_id
        
    async def stream_text_to_speech(self, text: str):
        """
        Convert text to speech using ElevenLabs API and return audio in µ-law format.
        
        Args:
            text: The text to convert to speech
            
        Returns:
            bytes: Audio data in µ-law format compatible with Twilio
        """
        try:
            # Generate audio using stream=False to get bytes directly instead of a generator
            audio_data = self.client.text_to_speech.convert(
                text=text,
                voice_id=self.voice_id,
                model_id="eleven_monolingual_v1",
                output_format="pcm_16000",  # 16kHz PCM format
                stream=False  # Important: Get bytes directly, not a generator
            )
            
            # Convert PCM audio bytes to µ-law format for Twilio
            # First, convert from 16kHz to 8kHz (Twilio requires 8kHz)
            
            # Convert to 16-bit signed integer PCM at 8kHz
            resampled_audio = audioop.ratecv(audio_data, 2, 1, 16000, 8000, None)[0]
            
            # Convert to µ-law format (expected by Twilio)
            mulaw_audio_bytes = audioop.lin2ulaw(resampled_audio, 2)
            
            return mulaw_audio_bytes
            
        except Exception as e:
            print(f"ElevenLabs error: {e}")
            raise
            
    async def list_available_voices(self):
        """
        List all available voices from ElevenLabs.
        
        Returns:
            list: List of Voice objects
        """
        return self.client.voices.get_all()
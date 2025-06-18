from elevenlabs.client import ElevenLabs
from app.config import settings

class ElevenLabsService:
    def __init__(self):
        """Initialize the ElevenLabs service with API key from settings"""
        self.client = ElevenLabs(api_key=settings.elevenlabs_apikey)
        # self.voice_id = settings.elevenlabs_voice_id

    async def stream_text_to_speech(self, text: str, voice: str, model: str = "eleven_multilingual_v1"):
        """
        Convert text to speech using ElevenLabs API and return complete μ-law encoded audio.
        
        Args:
            text (str): The text to convert to speech
        
        Returns:
            bytes: Complete μ-law encoded audio (8kHz) compatible with Twilio
        """
        print(f"ElevenLabs text_to_speech: {text}")

        try:
            # Get audio data from ElevenLabs in μ-law format
            audio_generator = self.client.text_to_speech.convert(
                text=text,
                voice_id=voice,
                model_id=model,
                output_format="ulaw_8000"
            )
            
            # Collect all chunks into a single bytes object
            audio_chunks = []
            for chunk in audio_generator:
                audio_chunks.append(chunk)
            
            mulaw_audio = b''.join(audio_chunks)
            return mulaw_audio
            
        except Exception as e:
            print(f"ElevenLabs error: {e}")
            raise

    async def list_available_voices(self):
        """
        List all available voices from ElevenLabs.
        
        Returns:
            list: List of Voice objects
        """
        voices = self.client.voices.search(include_total_count=True)
        print("Available voices:")
        for voice in voices.voices:
            print(f"ID: {voice.voice_id}, Name: {voice.name}")
        return voices
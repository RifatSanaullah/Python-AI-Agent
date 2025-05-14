import audioop
from elevenlabs.client import ElevenLabs
from app.config import settings

class ElevenLabsService:
    def __init__(self):
        """Initialize the ElevenLabs service with API key from settings"""
        self.client = ElevenLabs(api_key=settings.elevenlabs_apikey)
        self.voice_id = settings.elevenlabs_voice_id

    async def stream_text_to_speech(self, text: str):
        """
        Convert text to speech using ElevenLabs API and return complete audio.
        
        Args:
            text (str): The text to convert to speech
        
        Returns:
            bytes: Complete µ-law encoded audio (8kHz) compatible with Twilio
        """
        print(f"ElevenLabs text_to_speech: {text}")

        try:
            # Get audio data from ElevenLabs
            audio_generator = self.client.text_to_speech.convert(
                text=text,
                voice_id=self.voice_id,
                model_id="eleven_monolingual_v1",
                output_format="pcm_16000"  # 16kHz PCM format
            )
            
            # Collect all chunks into a single bytes object
            audio_chunks = []
            for chunk in audio_generator:
                audio_chunks.append(chunk)
            
            audio_data = b''.join(audio_chunks)
            
            # Convert from 16kHz to 8kHz (2 bytes/sample, mono)
            resampled_audio = audioop.ratecv(audio_data, 2, 1, 16000, 8000, None)[0]
            
            # Convert to µ-law format (Twilio expects 8-bit µ-law)
            mulaw_audio = audioop.lin2ulaw(resampled_audio, 2)
            
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
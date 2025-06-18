import asyncio

from app.config import settings
from pyht import Client
from pyht.client import TTSOptions , Format
import os

class PlayHT:
    def __init__(self , on_transcript = None ,on_start=None):

        self.client = Client(
            user_id=settings.playht_id,
            api_key=settings.playht_apikey,
        )
        self.options = TTSOptions(
            voice="s3://voice-cloning-zero-shot/775ae416-49bb-4fb6-bd45-740f205d20a1/jennifersaad/manifest.json",
            format=Format.FORMAT_MULAW,
            sample_rate=8000,
            speed=1,
            temperature=0.7,
            top_p=0.35,
            repetition_penalty=3,
            voice_guidance=0,
            style_guidance=0.5,
            text_guidance=0.75,
        )
        
        # self.lock_exit = threading.Lock()
        # self.exit = False

    async def stream_text_to_speech(self, text: str, call_id, func):
        try:
            response = self.client.tts(text, self.options, voice_engine = 'PlayDialog-http')
            for chunk in response:
            # do something with the audio chunk
                await func(call_id, chunk)

        except Exception as e:
            print(f"An error occurred: {e}")
            raise

# 'PlayDialog-http'
   
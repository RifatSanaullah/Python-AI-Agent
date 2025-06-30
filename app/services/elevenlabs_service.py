from elevenlabs.client import ElevenLabs
from app.config import settings
import websockets, asyncio, json
class ElevenLabsService:
    def __init__(self):
        """Initialize the ElevenLabs service with API key from settings"""
        self.client = ElevenLabs(api_key=settings.elevenlabs_apikey)
        self.ws = None
        # self.voice_id = settings.elevenlabs_voice_id
        self.queue_audio = {}
        self.text_queue = asyncio.Queue()


    async def update_call_id(self, call_id, queue_audio=None):
        self.queue_audio = {
                'call_id': call_id,
                "queue_audio": queue_audio
            }

    async def stream_text_to_speech(self, text: str, voice: str, model: str):
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
            audio_generator = self.client.text_to_speech.stream(
                text=text,
                voice_id=voice,
                model_id=model,
                output_format="ulaw_8000"
            )
            
            # Collect all chunks into a single bytes object
            audio_chunks = []
            for chunk in audio_generator:
                if chunk:
                    await queue_audio(call_id,chunk)
                    audio_chunks.append(chunk)
            
            mulaw_audio = b''.join(audio_chunks)
            return mulaw_audio
            
        except Exception as e:
            print(f"ElevenLabs error: {e}")
            raise

    # async def stream_text_to_speech(self, text, call_id, queue_audio=None):
    #     self.queue_audio = {
    #             'call_id': call_id,
    #             "queue_audio": queue_audio
    #         }
    #     await self.text_queue.put(text)

    # async def establish_connection(self, voice_id, model_id):
    #     """
    #     Establish a connection to the ElevenLabs API.
    #     This is a placeholder method as the ElevenLabs client handles connections internally.
    #     """
    #     # The ElevenLabs client manages its own connection, so no explicit connection setup is needed.
    #     url =f"wss://api.elevenlabs.io/v1/text-to-speech/{voice_id}/stream-input?model_id={model_id}&output_format=ulaw_8000"
    #     headers = {
    #     "xi-api-key": settings.elevenlabs_apikey,
    #     "accept": "application/json",
    #     "content-type": "application/json",
    #     }

    #     # Connect to ElevenLabs TTS
    #     async with websockets.connect(url, extra_headers=headers) as ws:
    #         await ws.send(json.dumps({
    #             "text": "",
    #             "voice_settings": {
    #                 "stability": 0.5,
    #                 "similarity_boost": 0.75
    #             },
    #             "output_format": "ulaw_8000"
    #         }))
    #         self.ws = ws
    #         while True:
    #             text = await self.text_queue.get()
    #             await ws.send(json.dumps({"text": text}))
    #             while True:
    #                 try:
    #                     msg = await ws.recv()
    #                     data = json.loads(msg)
    #                     if data.get("audio"):
    #                         # yield base64.b64decode(data["audio"])
    #                         await self.queue_audio['queue_audio'](self.queue_audio['call_id'],msg)
    #                     elif data.get('isFinal'):
    #                         print("[✓] Done speaking current sentence.")
    #                         break
    #                     # if isinstance(msg, bytes):
                            

    #                 except websockets.exceptions.ConnectionClosed:
    #                     break


    async def flush_sp_ws(self):
        """
        Flush the WebSocket connection to ensure all messages are sent.
        This is a placeholder method as the ElevenLabs client handles flushing internally.
        """
        if self.ws:
            await self.ws.send(json.dumps({"text": ""}))
    async def disconnect(self):
        return

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
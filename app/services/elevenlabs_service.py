from elevenlabs.client import ElevenLabs
from app.config import settings
import websockets, asyncio, json, re, base64
from app.services.interval_runner import IntervalRunner
from app.services.ai_service import AIService
class ElevenLabsService:
    def __init__(self, loop=None):
        """Initialize the ElevenLabs service with API key from settings"""
        self.client = ElevenLabs(api_key=settings.elevenlabs_apikey)
        self.ws = None
        # self.voice_id = settings.elevenlabs_voice_id
        self.queue_audio = {}
        self.text_queue = asyncio.Queue()
        self.voice_id = None
        self.voice = None
        self.model = None
        self.full_text_buffer = ''
        self.last_split_index = 0        
        self.ai_service = AIService()
        self.websocket= None
        self.ws_task= None
        self.audio_chunks=[]
        self.runner = IntervalRunner()

    async def update_call_id(self, call_id, queue_audio=None):
        self.queue_audio = queue_audio
        self.call_id = call_id

    async def stream_text_to_speech(self, text_chunk, chunk_id):
        self.full_text_buffer += text_chunk
        sentences_to_process = []
        self.last_split_index = 0

        # Improved regex:
        # Match a period/question mark/exclamation only if:
        # - not part of ellipsis (...)
        # - not followed by dash/hyphen
        pattern = r'(?<!\.)[.!?](?![.\-])(?:\s|$)'  # avoid splitting on ... or .-

        for match in re.finditer(pattern, self.full_text_buffer):
            sentence = self.full_text_buffer[self.last_split_index : match.end()].strip()
            if sentence:
                sentences_to_process.append(sentence)
            self.last_split_index = match.end()

        for sentence_to_speak in sentences_to_process:
            await self.send_stream_to_tts(sentence_to_speak, chunk_id)
            
        self.full_text_buffer = self.full_text_buffer[self.last_split_index:].strip()

    # async def send_to_tts(self, text: str):
    #     """
    #     Convert text to speech using ElevenLabs API and return complete μ-law encoded audio.
        
    #     Args:
    #         text (str): The text to convert to speech
        
    #     Returns:
    #         bytes: Complete μ-law encoded audio (8kHz) compatible with Twilio
    #     """
    #     print(f"ElevenLabs text_to_speech: {text}")

    #     try:
    #         # Get audio data from ElevenLabs in μ-law format
    #         audio_generator = self.client.text_to_speech.stream(
    #             text=text,
    #             voice_id=self.voice,
    #             model_id=self.model,
    #             output_format="ulaw_8000"
    #         )
            
    #         # Collect all chunks into a single bytes object
    #         audio_chunks = []
    #         for chunk in audio_generator:
    #             if chunk:
    #                 audio_chunks.append(chunk)
            
    #         mulaw_audio = b''.join(audio_chunks)
    #         await self.queue_audio(self.call_id, mulaw_audio)

    #         return mulaw_audio
            
    #     except Exception as e:
    #         print(f"ElevenLabs error: {e}")
    #         raise

    # async def establish_connection(self, voice: str, model: str):

    #     self.voice = voice
    #     self.model = model

    async def send_stream_to_tts(self, text, chunk_id):
        print("Text To speak: ",text)
        await self.websocket.send(json.dumps({
                "text": text,
                "flush" : True,
                "context_id" : chunk_id,
                "voice_settings": {
                    "stability": self.voice.get('temperature', 0.4),
                    "similarity_boost": self.voice.get('similarity', 0.7),
                    "speed" : self.voice.get('speed', 0.99),
                    "style": self.voice.get('style_guidance', 0.2)
                },
                "output_format": "ulaw_8000"
            }))
        
    def update_tts_interrupt(self, status):
        pass

    async def establish_connection(self, voice, model_id):
        """
        Establish a connection to the ElevenLabs API.
        This is a placeholder method as the ElevenLabs client handles connections internally.
        """
        self.voice_id = voice['model']
        self.voice = voice
        self.model = model_id
        # The ElevenLabs client manages its own connection, so no explicit connection setup is needed.
        url =f"wss://api.elevenlabs.io/v1/text-to-speech/{self.voice_id}/multi-stream-input?model_id={model_id}&output_format=ulaw_8000"
        headers = {
        "xi-api-key": settings.elevenlabs_apikey,
        "accept": "application/json",
        "content-type": "application/json",
        }
        self.websocket = await websockets.connect(url, extra_headers=headers)
        self.is_connected = True
        print("Connected to Elevenlabs WebSocket")
        await self.start_synthesiser()
        self.runner.start_interval(self.call_id, 10, self.flush_sp_ws)
        # Start listening for audio data

    async def start_synthesiser(self):
        self.ws_task = asyncio.create_task(self._listen_for_audio())

    async def _listen_for_audio(self):
        # Connect to ElevenLabs TTS
        while True:
            try:
                message = await self.websocket.recv()
                data = json.loads(message)
                if data.get("audio"):
                    # yield base64.b64decode(data["audio"])
                    contextId = data.get('contextId')
                    interrupted = False
                    if contextId != 'Greeting':
                        interrupted = self.ai_service.get_interrupt_status(self.call_id, contextId)
                    if interrupted is False:
                        await self.queue_audio(self.call_id, base64.b64decode(data["audio"]), contextId)
                    # self.audio_chunks.append(base64.b64decode(data["audio"]))

                if data.get('isFinal'):
                    # combined_audio = b''.join(self.audio_chunks)
                    # await self.queue_audio(self.call_id, combined_audio)

                    print("[✓] Done speaking current sentence.")

            except websockets.exceptions.ConnectionClosed:
                print("Elevenlabs WebSocket connection closed")
                self.websocket = None
                break
            except Exception as e:
                print(f"Error listening to Elevenlabs audio: {e}")
                break


    async def flush_sp_ws(self):
        """
        Flush the WebSocket connection to ensure all messages are sent.
        This is a placeholder method as the ElevenLabs client handles flushing internally.
        """
        pass
        if self.websocket:
            await self.websocket.send(json.dumps({"text": " "}))

    async def disconnect(self):
        """Flush the Elevenlabs websocket connection"""
        self.runner.stop_interval(self.call_id)  # Stop it manually
        if self.websocket:
            await self.websocket.close()
            self.is_connected = False
        self.ws_task = None


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
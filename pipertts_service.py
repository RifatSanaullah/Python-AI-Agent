import asyncio
import base64
import json
import wave
import io
import re
import websockets
from piper import PiperVoice
from piper.config import SynthesisConfig
from app.helpers.utils import filter_sentences_by_keywords
from pydub import AudioSegment

# Assuming Piper voice model and config are accessible globally or passed in
VOICE_MODEL_PATH = "D:/Verbacall/com.boomershub.ai.agent/piper_voices/en_US-libritts-high.onnx"
voice = PiperVoice.load(VOICE_MODEL_PATH, use_cuda=True)
syn_config = SynthesisConfig(
    speaker_id=27,
    length_scale=1.0,
    noise_scale=0.667,
    # noise_w_scale=0.8
)

class PiperService:
    def __init__(self, loop=None):
        """Initialize the Piper service"""
        self.queue_audio = None
        self.text_queue = asyncio.Queue()
        self.call_id = None
        self.full_text_buffer = ''
        self.last_split_index = 0
        self.websocket = None
        self.is_connected = False

    async def update_call_id(self, call_id, queue_audio=None):
        """Update the current call ID and audio queue callback."""
        self.call_id = call_id
        self.queue_audio = queue_audio

    async def stream_text_to_speech(self, text_chunk, chunk_id):
        self.full_text_buffer += text_chunk
        sentences_to_process = []
        self.last_split_index = 0
        pattern = r'(?<!\.)[.!?](?![.\-])(?:\s|$)'  # avoid splitting on ... or .-

        for match in re.finditer(pattern, self.full_text_buffer):
            sentence = self.full_text_buffer[self.last_split_index: match.end()].strip()
            if sentence:
                sentences_to_process.append(sentence)
            self.last_split_index = match.end()

        for sentence_to_speak in sentences_to_process:
            await self.send_stream_to_tts(sentence_to_speak, chunk_id)

        self.full_text_buffer = self.full_text_buffer[self.last_split_index:].strip()

    async def send_stream_to_tts(self, text, chunk_id):
        """
        Synthesize text to audio using Piper and convert to ulaw 8000 Hz.
        This method will block until synthesis and conversion are complete.
        """
        print("Text to speak (Piper): ", text)
        text = filter_sentences_by_keywords(text)
        loop = asyncio.get_running_loop()
        try:
            # Use run_in_executor to perform synchronous synthesis and conversion
            ulaw_data = await loop.run_in_executor(
                None,
                self._synthesize_and_convert_audio_sync,
                text
            )
            # Encode the ulaw audio data to base64
            encoded_audio = base64.b64encode(ulaw_data).decode('utf-8')
            message = {
                "audio": encoded_audio,
                "isFinal": True,
                "contextId": chunk_id
            }
            await self._simulate_websocket_message(json.dumps(message))
        except Exception as e:
            print(f"Piper synthesis and conversion error: {e}")

    def _synthesize_and_convert_audio_sync(self, text):
        """Synchronous function to perform Piper synthesis and convert to ulaw, with an optional MP3 save."""
        # Step 1: Synthesize audio to an in-memory WAV file
        wav_io = io.BytesIO()
        with wave.open(wav_io, "wb") as wav_file:
            voice.synthesize_wav(
                text,
                wav_file,
                syn_config=syn_config
            )
        wav_io.seek(0)

        # Step 2: Use pydub to load, resample, and convert to ulaw 8000 Hz
        audio_segment = AudioSegment.from_wav(wav_io)
        ulaw_audio_io = io.BytesIO()

        audio_segment.set_frame_rate(8000).set_channels(1).export(
            ulaw_audio_io,
            format="wav",
            parameters=["-acodec", "pcm_mulaw"]
        )
        ulaw_audio_io.seek(0)
        return ulaw_audio_io.read()

    async def _simulate_websocket_message(self, message):
        """Simulate a WebSocket message to maintain the same data flow."""
        data = json.loads(message)
        if data.get("audio"):
            contextId = data.get('contextId')
            await self.queue_audio(self.call_id, base64.b64decode(data["audio"]), contextId)

        if data.get('isFinal'):
            print("[✓] Done speaking current sentence.")

    async def establish_connection(self, voice, model_id):
        """Mimic the connection establishment. Piper is local, so this just marks the service as connected."""
        self.is_connected = True
        print("Piper service is ready to synthesize.")

    async def flush_sp_ws(self):
        """
        Flush the WebSocket connection to ensure all messages are sent.
        This is a placeholder method as the ElevenLabs client handles flushing internally.
        """
        pass
        if self.websocket:
            await self.websocket.send(json.dumps({"text": " "}))

    def check_ws_connection(self):
        """Check if the service is ready (connected)."""
        return self.is_connected

    async def disconnect(self):
        """Mimic disconnection. For Piper, this just marks the service as disconnected."""
        self.is_connected = False
        print("Piper service disconnected.")




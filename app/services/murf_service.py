import asyncio
from app.config import settings
import re
from pyht.client import TTSOptions , Format

from murf import Murf

class AudioChunk:
    """Represents an audio chunk with metadata"""
    data: bytes
    timestamp: float
    chunk_id: str
    is_final: bool = False
class MurfAI:
    def __init__(self, loop=None):

        self.client = Murf(api_key="ap2_bf0163e0-d8f3-437f-bd7f-61e1c14f215f")
        self.options = None
        self.queue_audio = None
        self.call_id = None
        self.voice_engine = "PlayDialog"
        self.full_text_buffer = ''
        self.last_split_index = 0
        # self.lock_exit = threading.Lock()
        # self.exit = False

    async def update_call_id(self, call_id, queue_audio):
        self.queue_audio = queue_audio
        self.call_id = call_id

    async def establish_connection(self,  voice:str, model):
        self.voice_engine = "PlayDialog"
        """Establish connection to PlayHT API"""
        self.options = TTSOptions(
            voice=voice,
            format=Format.FORMAT_MULAW,
            sample_rate=8000,
            speed=1,
            temperature=0.9,
            top_p=0.9,
            repetition_penalty=6,
            voice_guidance=0,
            style_guidance=5,
            text_guidance=0.2,
        )
        if self.voice_engine == 'PlayDialog' or self.voice_engine == 'PlayDialogMultilingual':
            self.options=  TTSOptions(
                voice=voice,
                format=Format.FORMAT_MULAW,
                sample_rate=8000,
                speed=1,
                temperature=1.02,
                voice_conditioning_seconds=20,

            )
                    
        print(f"PlayHT connection established with voice: {voice}, model: {model}")
            
        # Start listening for audio data

    async def start_synthesiser(self, text):

        asyncio.create_task(self.send_audio(text))

    async def stream_text_to_speech(self, text: str):
        try:
            # do something with the audio chunk
            await self.send_to_tts(text)

        except Exception as e:
            print(f"An error occurred: {e}")
            raise
        
    async def send_stream_to_tts(self, text):
        await self.send_audio(text)

    async def send_audio(self, text):
        res = self.client.text_to_speech.stream(
            text=text,
            style = "Conversational",
            voice_id="en-US-natalie",
            format="ULAW",
            sample_rate=8000,
            pitch = 0
        )
        for audio_chunk in res:
            await self.queue_audio(self.call_id, audio_chunk)

    async def send_to_tts(self, text_chunk):
        
        self.full_text_buffer += text_chunk

        sentences_to_process = []
        self.last_split_index = 0
        
        # Loop to find all complete sentences within the current buffer
        for match in re.finditer(r'[.!?](?:\s|$)', self.full_text_buffer):
            # The sentence goes from the last split point up to the end of this punctuation mark
            sentence = self.full_text_buffer[self.last_split_index : match.end()].strip()
            if sentence:
                sentences_to_process.append(sentence)
            self.last_split_index = match.end()

        # If we found any complete sentences, process them
        for sentence_to_speak in sentences_to_process: 
            await self.send_audio(sentence_to_speak)
        # await self._synthesize_text_chunk(text_to_synthesize, self.current_synth_id)
            # self.full_text_buffer = ''
            
        # Keep any remaining text in the buffer for the next chunk
        self.full_text_buffer = self.full_text_buffer[self.last_split_index:].strip()

    async def flush_sp_ws(self):
        """Flush the PlayHT websocket connection"""
        return

    async def disconnect(self):
        """Flush the PlayHT websocket connection"""
        return


# 'PlayDialog-http'
   
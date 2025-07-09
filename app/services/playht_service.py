import asyncio
import base64, json  # Add this import

from app.config import settings
from pyht import AsyncClient
from pyht.client import TTSOptions , Format
import os, re, time
import aiohttp, websockets

class AudioChunk:
    """Represents an audio chunk with metadata"""
    data: bytes
    timestamp: float
    chunk_id: str
    is_final: bool = False
class PlayHT:
    def __init__(self, loop=None):

        self.client = AsyncClient(
            user_id=settings.playht_id,
            api_key=settings.playht_apikey,
        )
        self.base_url = "https://api.play.ht/api/v2"
        self.options = None
        self.queue_audio = None
        self.call_id = None
        self.loop = loop or asyncio.get_event_loop()
        self.voice_engine = "PlayDialog"
        self.full_text_buffer = ''
        self.last_split_index = 0
        self.headers = {
            "accept": "*/*",
            "Authorization": f"Bearer {settings.playht_apikey}",
            "X-User-ID": settings.playht_id,
            "Content-Type": "application/json"
        }

        self.websocket = False
        self.websocket_url = ""
        self.is_connected = False
        self.audio_chunks=[]
        self.current_request_id=None
        # self.lock_exit = threading.Lock()
        # self.exit = False
    async def _get_websocket_url(self):
        """Get WebSocket URL from PlayHT auth endpoint"""
        try:
            headers = {
                "Authorization": f"Bearer {settings.playht_apikey}",
                "X-User-ID": settings.playht_id,
                "Content-Type": "application/json"
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    "https://api.play.ht/api/v4/websocket-auth",
                    headers=headers
                ) as response:
                    if response.status == 200 or response.status == 201:
                        data = await response.json()
                        websocket_urls = data.get("websocket_urls", {})
                    
                        if self.voice_engine in websocket_urls:
                            self.websocket_url = websocket_urls[self.voice_engine]
                            print(f"Got WebSocket URL for {self.voice_engine}")
                            return True
                        else:
                            print(f"Engine {self.voice_engine} not found in available engines: {list(websocket_urls.keys())}")
                            return False
                    else:
                        print(f"Failed to get WebSocket URL: {response.status}")

                        return False
                        
        except Exception as e:
            print(f"Error getting WebSocket URL: {e}")
            return False

    async def update_call_id(self, call_id, queue_audio):
        self.queue_audio = queue_audio
        self.call_id = call_id

    async def establish_connection(self,  voice:str, model):
        self.voice_engine = model
        """Establish connection to PlayHT API"""
        if not await self._get_websocket_url():
            print("Failed to get WebSocket URL")
            return False
            
        self.options=  {
                        "voice": voice,
                        "sample_rate": 48000,
                        "output_format": "mulaw",
                        "speed": 1.1,
                        "temperature": 1.02,
                        "top_p": 0.9,
                        "repetition_penalty": 5,
                        "length_penalty": 1.0,
                        "voice_guidance": 0,
                        "style_guidance": 5,
                        "text_guidance": 0.2
                    }
        if self.voice_engine == 'PlayDialog' or self.voice_engine == 'PlayDialogMultilingual':
            self.options=  {
                        "voice": voice,
                        "sample_rate": 48000,  
                        "output_format": "mulaw",
                        "speed": 1,
                        "temperature": 1.02,
                        "voice_conditioning_seconds" : 20,
                    }
                    
        print(f"PlayHT connection established with voice: {voice}, model: {model}")
            
        self.websocket = await websockets.connect(self.websocket_url)
        self.is_connected = True
        print("Connected to PlayHT WebSocket")
        await self.start_synthesiser()
        # Start listening for audio data

    async def start_synthesiser(self):
        asyncio.create_task(self._listen_for_audio())

    async def stream_text_to_speech(self, text: str):
        try:
            # do something with the audio chunk
            await self.send_to_tts(text)


        except Exception as e:
            print(f"An error occurred: {e}")
            raise
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
            self.options['text'] = sentence_to_speak
            message = self.options    
            await self.websocket.send(json.dumps(message))
        # await self._synthesize_text_chunk(text_to_synthesize, self.current_synth_id)
            # self.full_text_buffer = ''
            
        # Keep any remaining text in the buffer for the next chunk
        self.full_text_buffer = self.full_text_buffer[self.last_split_index:].strip()

    async def _listen_for_audio(self):
            """Listen for incoming audio data from PlayHT"""
            try:
                async for message in self.websocket:
                    try:
                    # First, try to determine if this is binary or text data
                        if isinstance(message, bytes):
                            # This is binary audio data
                            self.audio_chunks.append(message)

                        else:
                            # This should be a text/JSON message
                            try:
                                # Handle both string and bytes that contain JSON
                                if isinstance(message, bytes):
                                    message_str = message.decode('utf-8')
                                else:
                                    message_str = message
                                    
                                data = json.loads(message_str)
                                
                                if data.get("type") == "start":
                                    self.current_request_id = data.get("request_id")
                                    self.audio_chunks = []  # Reset for new request
                                    print(f"Started processing request: {self.current_request_id}")
                                    
                                elif data.get("type") == "end":
                                    # Final chunk with all audio combined
                                    if self.audio_chunks:
                                        combined_audio = b''.join(self.audio_chunks)
                                        await self.queue_audio(self.call_id, combined_audio)
                                    
                                    print(f"Finished processing request: {self.current_request_id}")
                                    self.current_request_id = None
                                    
                                elif data.get("status") and data.get("status") != 200:
                                    print(f"PlayHT error: Status {data.get('status')}, Message: {data}")
                                    
                            except (json.JSONDecodeError, UnicodeDecodeError) as decode_error:
                                # If JSON parsing fails, this might be binary data that we missed
                                        print(f"Failed to parse message as JSON or audio: {decode_error}")
                                        print(f"Message preview: {message[:100] if len(str(message)) > 100 else message}")
                                
                    except Exception as msg_error:
                        print(f"Error processing individual message: {msg_error}")
                        print(f"Message type: {type(message)}, Length: {len(message) if hasattr(message, '__len__') else 'N/A'}")
                    
            except websockets.exceptions.ConnectionClosed:
                print("PlayHT WebSocket connection closed")
                self.is_connected = False
            except Exception as e:
                print(f"Error listening to PlayHT audio: {e}")

    async def flush_sp_ws(self):
        """Flush the PlayHT websocket connection"""
        return

    async def disconnect(self):
        """Flush the PlayHT websocket connection"""
        if self.websocket:
            await self.websocket.close()
            self.is_connected = False


# 'PlayDialog-http'
   
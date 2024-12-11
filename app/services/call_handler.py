import base64
from sqlalchemy.orm import Session
from app.services.twilio_service import TwilioService
from app.services.chatgpt_service import ChatGPTService
from app.services.polly_service import PollyService
from app.services.deepgram_service import DeepgramService
from app.services.assembly_ai_transcribe_service import TranscribeService
from websockets.exceptions import ConnectionClosedError, ConnectionClosedOK
import logging
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    # format='%(asctime)s.%(msecs)03d - %(levelname)s - %(message)s',
    # datefmt='%Y-%m-%d %H:%M:%S'
)
class CallHandler:
    def __init__(self, db: Session):
        self.db = db
        self.twilio_service = TwilioService()
        self.chatgpt_service = ChatGPTService()
        self.stream_sid = None
        self.polly_service = PollyService()
        self.deepgram_transcribe_service = DeepgramService(on_transcript=self.handle_transcript, on_start=self.on_user_speech)
        self.transcribe_service = TranscribeService(on_transcript=self.handle_transcript)
        self.max_chunk_size = 200
        self.background_sound = False
        self.ai_speaking = False

    async def process_input(self, websocket):
        self.websocket = websocket
        self.deepgram_transcribe_service.establishDGConnection()
        await websocket.accept()
        try:
            while True:
                data = await websocket.receive_json()
                if data["event"] in ("connected", "start"):
                    print(f"Media WS: Received event '{data['event']}'")
                    continue
                if data["event"] == "media":
                    media = data["media"]
                    chunk = media["payload"]
                    chunk_bytes = base64.b64decode(chunk)
                    await self.twilio_service.audio_buffer.put(chunk_bytes) 

                if not self.twilio_service.response_buffer.empty():
                    print("Processing response buffers...")
                    response_audio = await self.twilio_service.response_buffer.get()
                    # await self.twilio_service.send_control_command(self.websocket, 'stop')
                    if self.background_sound is True:
                        await self.stop_stream()
                    self.ai_speaking = True
                    await self.twilio_service.send_audio_stream(self.websocket, self.stream_sid, response_audio)

                if not self.twilio_service.audio_buffer.empty():
                    audio_data = await self.twilio_service.audio_buffer.get()
                    # await self.transcribe_service.transcribe(audio_data)
                    await self.deepgram_transcribe_service.transcribe(audio_data)

                    

        except ConnectionClosedError as e:
            print(f"Connection closed with error: {e.code} - {e.reason}")
        except ConnectionClosedOK as e:
            print(f"Connection closed normally: {e.code} - {e.reason}")
        except Exception as e:
            print("Unexpected error:", e)
        finally:
            print("WebSocket connection closed.")
            await websocket.close()
            self.transcribe_service.close()  # Close the transcriber service
            
    async def stop_stream(self):
        await self.twilio_service.stop_audio_stream(self.websocket, self.stream_sid)
        self.background_sound = False

    async def on_user_speech(self):
        if self.ai_speaking:
            await self.stop_stream()
            self.ai_speaking = False

    async def handle_transcript(self, transcript):
        print(f"Transcript: {transcript}")
        await self.enable_background_sound(True)
        response = await self.chatgpt_service.generate_response(transcript, self.db)
        print(f"Response: {response}")
        await self.synthesize_response(response)

    def chunk_text(self, text, chunk_size):
        chunks = []
        words = text.split()
        current_chunk = ''
        for word in words:
            if len(current_chunk) + len(word) <= chunk_size:
                current_chunk += ' ' + word
            else:
                chunks.append(current_chunk.strip())
                current_chunk = word
        if current_chunk:
            chunks.append(current_chunk.strip())
        return chunks
    
    async def synthesize_response(self, text: str):
        # Chunk the text into smaller parts
        text_chunks = self.chunk_text(text, self.max_chunk_size)
        
        # Synthesize audio for each chunk
        for i, chunk in enumerate(text_chunks):
            print(f"\nProcessing chunk {i + 1}...{chunk}\n")

            start_time = datetime.now()
            # audio_stream = await self.polly_service.stream_text_to_speech(chunk)
            audio_stream = await self.deepgram_transcribe_service.stream_text_to_speech(chunk)
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds() * 1000  # Calculate duration in milliseconds
            logging.info(f"Total Deepgram duration: {duration:.3f} ms")
            await self.twilio_service.response_buffer.put(audio_stream)

        print('audio streamed')
        
    async def handle_call(self, call_id: str):
        print("Handling call...")
        response = self.twilio_service.initialize_call(call_id)
        self.transcribe_service.connect()  # Connect the transcriber service
        await self.synthesize_response("Hello and Welcome to BoomersHub!!")
        return response

    async def make_outgoing_call(self, phone_number: str):
        call_sid = self.twilio_service.make_call(phone_number)
        return call_sid

    async def handle_stream_callback(self, data):
        """Handle the stream callback to get the streamSid."""
        stream_sid = data.get("StreamSid")
        call_sid = data.get("CallSid")
        print(f"Stream SID: {stream_sid}, Call SID: {call_sid}")
        self.stream_sid = stream_sid
        return "OK", 200
    
    async def enable_background_sound(self ,status = False):

        self.background_sound = status
        if status is True:
            if not self.twilio_service.background_sound:
                audio_stream = await self.twilio_service.get_background_sound()
                self.twilio_service.background_sound = audio_stream
            await self.twilio_service.send_audio_stream(self.websocket, self.stream_sid, self.twilio_service.background_sound)


    

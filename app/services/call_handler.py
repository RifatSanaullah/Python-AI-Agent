import base64
from sqlalchemy.orm import Session
from app.services.twilio_service import TwilioService
from app.services.chatgpt_service import ChatGPTService
from app.services.polly_service import PollyService
from app.services.assembly_ai_transcribe_service import TranscribeService
from websockets.exceptions import ConnectionClosedError, ConnectionClosedOK

class CallHandler:
    def __init__(self, db: Session):
        self.db = db
        self.twilio_service = TwilioService()
        self.chatgpt_service = ChatGPTService()
        self.polly_service = PollyService()
        self.transcribe_service = TranscribeService(on_transcript=self.handle_transcript)
        self.stream_sid = None

    async def process_input(self, websocket):
        self.websocket = websocket
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
                    await self.twilio_service.send_audio_stream(self.websocket, self.stream_sid, response_audio)

                if not self.twilio_service.audio_buffer.empty():
                    audio_data = await self.twilio_service.audio_buffer.get()
                    await self.transcribe_service.transcribe(audio_data)
                    

        except ConnectionClosedError as e:
            print(f"Connection closed with error: {e.code} - {e.reason}")
        except ConnectionClosedOK as e:
            print(f"Connection closed normally: {e.code} - {e.reason}")
        except Exception as e:
            print("Unexpected error:", e)
        finally:
            print("WebSocket connection closed.")
            await websocket.close()

    async def handle_transcript(self, transcript):
        print(f"Transcript: {transcript}")
        response = await self.chatgpt_service.generate_response(transcript)
        print(f"Response: {response}")
        await self.synthesize_response(response)

    async def synthesize_response(self, text: str):
        audio_stream = await self.polly_service.stream_text_to_speech(text)
        await self.twilio_service.response_buffer.put(audio_stream)
        
    async def handle_call(self, call_id: str):
        print("Handling call...")
        response = self.twilio_service.initialize_call(call_id)
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

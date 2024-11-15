# app/services/call_handler.py
import spacy
import re
import asyncio  # Add asyncio import
import base64  # Add base64 import
import numpy as np  # Add numpy import
from sqlalchemy.orm import Session
# from app.services.chatgpt_audio_service import ChatGPTAudioService
from app.utils.db_utils import save_conversation
from app.services.twilio_service import TwilioService
from app.services.chatgpt_service import ChatGPTService
from app.services.polly_service import PollyService
from app.services.transcribe_service import TranscribeService  # Add this import
from .knowledge_base_service import list_knowledge_entries
from websockets.exceptions import ConnectionClosedError, ConnectionClosedOK
from starlette.websockets import WebSocketDisconnect

class CallHandler:
    def __init__(self, db: Session):
        self.db = db
        self.twilio_service = TwilioService()
        self.chatgpt_service = ChatGPTService()
        # self.chatgpt_audio_service = ChatGPTAudioService()
        self.polly_service = PollyService()
        self.transcribe_service = TranscribeService()
        self.stream_sid = None

    async def process_input(self, websocket):
        self.websocket = websocket  # Store websocket instance
        await websocket.accept()
        # await self.start_background_task()  # Start the background task
        try:
            while True:
                data = await websocket.receive_json()
                if data["event"] in ("connected", "start"):
                    print(f"Media WS: Received event '{data['event']}'")
                    continue
                if data["event"] == "media":
                    media = data["media"]
                    chunk = base64.b64decode(media["payload"])
                    # Check for static noise
                    if self.is_static_noise(chunk):
                        print("Static noise detected, skipping chunk.")
                        continue
                    # Add incoming audio to buffer for transcription
                    await self.twilio_service.audio_buffer.put(chunk)  

                if not self.twilio_service.response_buffer.empty():
                    print("Processing response buffers...")
                    response_audio = await self.twilio_service.response_buffer.get()
                    await self.twilio_service.send_audio_stream(self.websocket, self.stream_sid, response_audio)

                # Process audio buffer for transcription
                if not self.twilio_service.audio_buffer.empty():
                    audio_data = await self.twilio_service.audio_buffer.get()
                    await self.transcribe_service.send_audio_chunk(audio_data)
                    async for transcript in self.transcribe_service.receive_transcriptions():
                        if transcript:
                            response = await self.chatgpt_service.generate_response(transcript)
                            print(f"Transcript: {transcript}")
                            print(f"Response: {response}")
                            await self.synthesize_response(response)

        except ConnectionClosedError as e:
            print(f"Connection closed with error: {e.code} - {e.reason}")
        except ConnectionClosedOK as e:
            print(f"Connection closed normally: {e.code} - {e.reason}")
        except Exception as e:
            print("Unexpected error:", e)
        finally:
            print("WebSocket connection closed.")
            await self.transcribe_service.close_transcription()
            await websocket.close()

    def is_static_noise(self, audio_chunk):
        """Check if the audio chunk is static noise."""
        audio_array = np.frombuffer(audio_chunk, dtype=np.int16)
        return np.mean(np.abs(audio_array)) < 10  # Threshold for static noise

    async def synthesize_response(self, text: str):
        audio_stream = await self.polly_service.stream_text_to_speech(text)
        await self.twilio_service.response_buffer.put(audio_stream)
        
    async def handle_call(self, call_id: str):
        print("Handling call...")
        response = self.twilio_service.initialize_call(call_id)
        await self.transcribe_service.start_transcription()
        await self.synthesize_response("Hello and Welcome to BoomersHub!!")
        return response

    async def handle_incoming_call(self, call_id: str, client_message: str, required_info: dict = {"name": None, "phone_number": None, "email": None}):
        nlp = spacy.load("en_core_web_sm")
        doc = nlp(client_message)
        knowledge_base = list_knowledge_entries(self.db)
        if not knowledge_base:
            knowledge_string = "Knowledge Base is empty."
        else:
            knowledge_string = "Knowledge Base:\n"
            for knowledge in knowledge_base:
                knowledge_string += f"{knowledge.question}: {knowledge.answer}\n"
        for entity in doc.ents:
            if entity.label_ == "PERSON":
                required_info["name"].append(entity.text)
        
        required_info["email"] = re.findall(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,7}\b", client_message)
        required_info["phone_number"] = re.findall(r"\b(\+?\d{1,2}\s?\(?\d{3}\)?\s?\d{3}[-\s]?\d{4})", client_message)
        response_message = await self.chatgpt_service.generate_response(client_message, knowledge_string)
        save_conversation(self.db, call_id, "client", client_message)
        save_conversation(self.db, call_id, "bot", response_message)
        audio_stream_url = self.polly_service.stream_text_to_speech(response_message)
        return audio_stream_url, required_info
    
    async def process_call(self, call_sid, speech_result):
        """Process the gathered speech result and update the fields needed."""
        call_state = self.twilio_service.active_calls.get(call_sid)

        print(call_state)
        
        if not call_state:
            return None, False

        field_status = call_state["fields_needed"]

        if not field_status["name"]:
            field_status["name"] = speech_result
            message = "Thank you. Now, please tell me your email."
        elif not field_status["email"]:
            field_status["email"] = speech_result
            message = "Thank you. Finally, please tell me your phone number."
        elif not field_status["phone_number"]:
            field_status["phone_number"] = speech_result
            call_state["is_complete"] = True
            self.twilio_service.hangup_call(call_sid)
            return None, True
        
        if not call_state["is_complete"]:
            response = await self.twilio_service.generate_voice_response(message)
        
        return response, call_state["is_complete"]

    async def make_outgoing_call(self, phone_number: str):
        call_sid = self.twilio_service.make_call(phone_number)
        return call_sid

    async def handle_stream_callback(self, data):
        """Handle the stream callback to get the streamSid."""
        stream_sid = data.get("StreamSid")
        call_sid = data.get("CallSid")
        print(f"Stream SID: {stream_sid}, Call SID: {call_sid}")
        # Store the streamSid in the CallHandler instance
        self.stream_sid = stream_sid
        return "OK", 200

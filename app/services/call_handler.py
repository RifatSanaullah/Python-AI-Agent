# import spacy
# import re
import base64
import numpy as np
from sqlalchemy.orm import Session
from app.utils.db_utils import save_conversation
from app.services.twilio_service import TwilioService
from app.services.chatgpt_service import ChatGPTService
from app.services.polly_service import PollyService
from app.services.transcribe_service import TranscribeService
from .knowledge_base_service import list_knowledge_entries
from websockets.exceptions import ConnectionClosedError, ConnectionClosedOK
import webrtcvad
from scipy.signal import butter, lfilter

class CallHandler:
    def __init__(self, db: Session):
        self.db = db
        self.twilio_service = TwilioService()
        self.chatgpt_service = ChatGPTService()
        self.polly_service = PollyService()
        self.transcribe_service = TranscribeService()
        self.stream_sid = None
        self.vad = webrtcvad.Vad()
        self.vad.set_mode(2)

    # High-pass filter for noise reduction
    def highpass_filter(self, audio, cutoff=300, fs=8000, order=5):
        nyquist = 0.5 * fs
        normal_cutoff = cutoff / nyquist
        b, a = butter(order, normal_cutoff, btype='high', analog=False)
        return lfilter(b, a, audio)
    
    # Function to check for silence/static
    def is_blank_or_static(self, audio_payload):
        audio_data = np.frombuffer(audio_payload, dtype=np.int16)
        rms = np.sqrt(np.mean(audio_data ** 2))
        if np.isnan(rms):
            return True
        silence_threshold = 500
        return rms < silence_threshold
    
    # Function to check for speech
    def is_speech(self, audio_payload):
        return self.vad.is_speech(audio_payload, sample_rate=8000)
    
    # Process valid audio
    async def process_valid_audio(self, audio_payload):
        audio_data = np.frombuffer(audio_payload, dtype=np.int16)
        filtered_audio = self.highpass_filter(audio_data)
        await self.twilio_service.audio_buffer.put(filtered_audio.tobytes())

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
                    chunk = media["payload"]
                    chunk_bytes = base64.b64decode(chunk)
                    # Check for static noise
                    if self.is_blank_or_static(chunk_bytes):
                        print("Blank or static audio detected, skipping chunk.")
                        continue
                    if self.is_speech(chunk_bytes):
                        # Add incoming audio to buffer for transcription
                        await self.process_valid_audio(chunk_bytes) 

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

    async def synthesize_response(self, text: str):
        audio_stream = await self.polly_service.stream_text_to_speech(text)
        await self.twilio_service.response_buffer.put(audio_stream)
        
    async def handle_call(self, call_id: str):
        print("Handling call...")
        response = self.twilio_service.initialize_call(call_id)
        await self.synthesize_response("Hello and Welcome to BoomersHub!!")
        await self.transcribe_service.start_transcription()
        return response

    # async def handle_incoming_call(self, call_id: str, client_message: str, required_info: dict = {"name": None, "phone_number": None, "email": None}):
    #     nlp = spacy.load("en_core_web_sm")
    #     doc = nlp(client_message)
    #     knowledge_base = list_knowledge_entries(self.db)
    #     if not knowledge_base:
    #         knowledge_string = "Knowledge Base is empty."
    #     else:
    #         knowledge_string = "Knowledge Base:\n"
    #         for knowledge in knowledge_base:
    #             knowledge_string += f"{knowledge.question}: {knowledge.answer}\n"
    #     for entity in doc.ents:
    #         if entity.label_ == "PERSON":
    #             required_info["name"].append(entity.text)
        
    #     required_info["email"] = re.findall(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,7}\b", client_message)
    #     required_info["phone_number"] = re.findall(r"\b(\+?\d{1,2}\s?\(?\d{3}\)?\s?\d{3}[-\s]?\d{4})", client_message)
    #     response_message = await self.chatgpt_service.generate_response(client_message, knowledge_string)
    #     save_conversation(self.db, call_id, "client", client_message)
    #     save_conversation(self.db, call_id, "bot", response_message)
    #     audio_stream_url = self.polly_service.stream_text_to_speech(response_message)
    #     return audio_stream_url, required_info
    
    # async def process_call(self, call_sid, speech_result):
    #     """Process the gathered speech result and update the fields needed."""
    #     call_state = self.twilio_service.active_calls.get(call_sid)

    #     print(call_state)
        
    #     if not call_state:
    #         return None, False

    #     field_status = call_state["fields_needed"]

    #     if not field_status["name"]:
    #         field_status["name"] = speech_result
    #         message = "Thank you. Now, please tell me your email."
    #     elif not field_status["email"]:
    #         field_status["email"] = speech_result
    #         message = "Thank you. Finally, please tell me your phone number."
    #     elif not field_status["phone_number"]:
    #         field_status["phone_number"] = speech_result
    #         call_state["is_complete"] = True
    #         self.twilio_service.hangup_call(call_sid)
    #         return None, True
        
    #     if not call_state["is_complete"]:
    #         response = await self.twilio_service.generate_voice_response(message)
        
    #     return response, call_state["is_complete"]

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

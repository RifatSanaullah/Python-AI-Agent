# app/services/call_handler.py
from sqlalchemy.orm import Session
from app.utils.db_utils import save_conversation
from app.services.twilio_service import TwilioService
from app.services.chatgpt_service import ChatGPTService
from app.services.polly_service import PollyService

class CallHandler:
    def __init__(self, db: Session):
        self.db = db
        self.twilio_service = TwilioService()
        self.chatgpt_service = ChatGPTService()
        self.polly_service = PollyService()

    async def handle_incoming_call(self, call_id: str, client_message: str):
        response_message = await self.chatgpt_service.generate_response(client_message)
        save_conversation(self.db, call_id, "client", client_message)
        save_conversation(self.db, call_id, "bot", response_message)
        audio_stream_url = self.polly_service.stream_text_to_speech(response_message)
        return audio_stream_url

    async def make_outgoing_call(self, phone_number: str):
        call_sid = self.twilio_service.make_call(phone_number)
        return call_sid

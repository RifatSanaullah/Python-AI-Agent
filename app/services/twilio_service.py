# app/services/twilio_service.py
from twilio.rest import Client
from app.config import settings

class TwilioService:
    def __init__(self):
        self.client = Client(settings.twilio_account_sid, settings.twilio_auth_token)

    def make_call(self, to: str):
        call = self.client.calls.create(
            to=to,
            from_=settings.twilio_phone_number,
            url=f"{settings.base_url}/incoming_call"  # Replace with your actual URL
        )
        return call.sid

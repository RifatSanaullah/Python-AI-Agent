# app/main.py
import os
from dotenv import load_dotenv
from fastapi import FastAPI, Request, Depends, Response
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from twilio.twiml.voice_response import VoiceResponse
from app.config import settings
from app.models.base import init_db, SessionLocal
from app.models.conversation import Conversation
from app.services.call_handler import CallHandler
from app.utils.db_utils import get_db

load_dotenv()

app = FastAPI()

# Initialize the database tables
init_db()

@app.get("/stream_audio")
async def stream_audio(text: str):
    from app.services.polly_service import PollyService
    polly_service = PollyService()
    audio_stream = polly_service.stream_text_to_speech(text)
    return StreamingResponse(audio_stream, media_type="audio/mpeg")


@app.post("/incoming_call")
async def incoming_call(request: Request, db: Session = Depends(get_db)):
    data = await request.json()
    call_id = data.get("call_id")
    client_message = data.get("client_message")

    call_handler = CallHandler(db)
    audio_stream_url = await call_handler.handle_incoming_call(call_id, client_message)

    response = VoiceResponse()
    response.play(audio_stream_url)

    return Response(content=str(response), media_type="application/xml")


@app.post("/outgoing_call")
async def outgoing_call(phone_number: str, db: Session = Depends(get_db)):
    call_handler = CallHandler(db)
    call_sid = await call_handler.make_outgoing_call(phone_number)
    return {"call_sid": call_sid}

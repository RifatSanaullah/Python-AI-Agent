# app/main.py
import uuid
from dotenv import load_dotenv
from fastapi import FastAPI, Request, Depends, Response, WebSocket
from fastapi.responses import StreamingResponse, PlainTextResponse
from sqlalchemy.orm import Session
from twilio.twiml.voice_response import VoiceResponse, Gather, Stream
from app.models.base import init_db
from app.services.call_handler import CallHandler
from app.utils.db_utils import get_db
from app.services.transcribe_service import TranscribeService
from app.services.twilio_service import TwilioService
from app.routes import knowledge_base
from contextlib import asynccontextmanager

load_dotenv()

app = FastAPI(
    title="BoomerCall API",
    description="API for Voice Assistant",
    version="0.0.2",
)

app.include_router(knowledge_base.router, prefix="/api", tags=["knowledge_base"])

# Initialize
init_db()

# Create a global CallHandler instance
call_handler_instance = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global call_handler_instance
    db = next(get_db())
    call_handler_instance = CallHandler(db)
    yield
    # Cleanup code if needed

app.router.lifespan_context = lifespan

def get_call_handler():
    return call_handler_instance

@app.websocket("/audio-stream")
async def audio_stream(websocket: WebSocket, call_handler: CallHandler = Depends(get_call_handler)):
    await call_handler.process_input(websocket)

@app.post("/incoming_call")
async def incoming_call(request: Request, call_handler: CallHandler = Depends(get_call_handler)):
    data = await request.form()
    call_id = data.get("CallSid")
    response = await call_handler.handle_call(call_id)
    return PlainTextResponse(content=str(response), media_type="application/xml")

@app.post("/outgoing_call")
async def outgoing_call(phone_number: str, call_handler: CallHandler = Depends(get_call_handler)):
    call_sid = await call_handler.make_outgoing_call(phone_number)
    return {"call_sid": call_sid}

@app.post("/gather")
async def gather(request: Request, call_handler: CallHandler = Depends(get_call_handler)):
    """Processes speech input and updates the required information."""
    data = await request.form()
    call_sid = data.get("CallSid")
    speech_result = data.get("SpeechResult")

    print(f"Call SID: {call_sid}, Speech Result: {speech_result}")

    response, is_complete = await call_handler.process_call(call_sid, speech_result)

    if response is None:
        return Response(status_code=400, content="Call not initialized.")
    
    return Response(content=str(response), media_type="application/xml")

@app.post("/gather_audio")
async def handle_audio(request: Request, call_handler: CallHandler = Depends(get_call_handler)):
    transcribe_service = TranscribeService()
    form_data = await request.form()
    recording_url = form_data.get("RecordingUrl")
    call_id = form_data.get("CallSid")
    speech_result = form_data.get("SpeechResult")
    required = request.query_params.get("required_info", ["name", "phone_number", "email"])
    required_info = {key: None for key in required}
    print(form_data, recording_url, call_id, required_info)
    
    if recording_url:
        # Generate a unique job name for Amazon Transcribe
        job_name = f"transcription-job-{uuid.uuid4()}"
        
        # Convert Twilio's audio file URL to a URL Amazon Transcribe can access (e.g., S3)
        # For simplicity, assume recording_url is an S3 URL accessible by Amazon Transcribe.
        transcription_text = transcribe_service.transcribe_audio(recording_url, job_name)
        audio_stream_url, info = await call_handler.handle_incoming_call(call_id, transcription_text, required_info)
        required = [key for key, value in info.items() if value is None]
        if required:
            gather = Gather(input="speech", action=f"/gather_audio?required={required}", method="POST")
            gather.say("Please say your message after the beep.")
            response = VoiceResponse()
            response.append(gather)
            return Response(content=str(response), media_type="application/xml")
        if audio_stream_url:
            response = VoiceResponse()
            response.play(audio_stream_url)
            return Response(content=str(response), media_type="application/xml")

        
        # Return transcription result
        return {"transcription": transcription_text}
    
    return {"error": "No audio file received."}

@app.post("/stream_callback")
async def stream_callback(request: Request, call_handler: CallHandler = Depends(get_call_handler)):
    data = await request.form()
    return await call_handler.handle_stream_callback(data)

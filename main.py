import os
from fastapi import FastAPI, Request, Depends
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from twilio.twiml.voice_response import VoiceResponse
import services
from database import SessionLocal, Conversation
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

app = FastAPI()

# Middleware to allow CORS for Twilio
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Dependency to get the database session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@app.post("/incoming_call/")
async def handle_incoming_call(request: Request):
    response = VoiceResponse()
    response.say("Please say something after the beep.")
    response.record(timeout=10, transcribe=True, maxLength=30, action="/handle_recording", 
                    transcribeCallback="/transcription_complete")
    return str(response)

@app.post("/handle_recording/")
async def handle_recording(request: Request, db: Session = Depends(get_db)):
    recording_url = request.form.get('RecordingUrl')

    transcription_result = services.transcribe_audio(recording_url)
    client_input = transcription_result['results']['transcripts'][0]['transcript']
    
    client_number = request.form.get('From')
    context = services.get_context(client_number)

    prompt = services.build_prompt(client_number, client_input)
    gpt_response = services.get_chatgpt_response(prompt)

    extracted_info = services.extract_information(client_input)

    services.update_context(client_number, client_input, gpt_response)

    audio_stream = services.synthesize_speech(gpt_response)

    response = VoiceResponse()
    response.play(audio_stream)
    response.say("Goodbye!")

    conversation = Conversation(
        client_input=client_input,
        gpt_response=gpt_response,
        timestamp=str(datetime.now())
    )
    db.add(conversation)
    db.commit()

    return {
        "response": str(response),
        "extracted_info": extracted_info
    }

@app.post("/make_call/")
async def make_call_endpoint(to_phone_number: str):
    print(to_phone_number)
    call_sid = services.make_call(to_phone_number)  # Call the service function
    return {"message": "Call initiated successfully", "call_sid": call_sid}

@app.post("/handle_outgoing_call")
def handle_outgoing_call():
    response = VoiceResponse()
    response.say("Hello, this is a call from your FastAPI application.")
    response.say("Thank you for answering.")
    response.hangup()
    return str(response)

@app.post("/configure_voice/")
async def configure_voice(client_number: str, voice_id: str = 'Joanna', rate: str = 'medium', pitch: str = 'medium', volume: str = 
'medium'):
    services.update_context(client_number, None, None, {
        'voice_id': voice_id,
        'rate': rate,
        'pitch': pitch,
        'volume': volume
    })
    return {"message": "Voice configuration updated successfully."}


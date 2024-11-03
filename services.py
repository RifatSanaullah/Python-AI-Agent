import openai
import boto3
from twilio.rest import Client
import io
import os
from dotenv import load_dotenv
from fastapi import HTTPException

# Load environment variables from .env file
load_dotenv()

# AWS and Twilio setup
AWS_ACCESS_KEY = os.getenv("AWS_ACCESS_KEY")
AWS_SECRET_KEY = os.getenv("AWS_SECRET_KEY")
AWS_REGION_POLLY = os.getenv("AWS_REGION_POLLY")
AWS_REGION_TRANSCRIBE = os.getenv("AWS_REGION_TRANSCRIBE")
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_PHONE_NUMBER = os.getenv("TWILIO_PHONE_NUMBER")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Initialize AWS clients with specified regions
polly_client = boto3.client(
    'polly',
    aws_access_key_id=AWS_ACCESS_KEY,
    aws_secret_access_key=AWS_SECRET_KEY,
    region_name=AWS_REGION_POLLY
)

transcribe_client = boto3.client(
    'transcribe',
    aws_access_key_id=AWS_ACCESS_KEY,
    aws_secret_access_key=AWS_SECRET_KEY,
    region_name=AWS_REGION_TRANSCRIBE
)

# Twilio client setup
twilio_client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)

# Predefined context and knowledge base
PREDEFINED_CONTEXT = {
    "greeting": "You are a helpful assistant who provides information about our services.",
    "product_info": "You can provide information about our products including pricing, features, and availability.",
    "support": "You assist users in troubleshooting common issues.",
}

# Keywords for information extraction
EXTRACTION_KEYWORDS = {
    "name": ["name", "my name is", "I'm called"],
    "issue": ["issue", "problem", "trouble", "difficulty"],
    "request": ["request", "need", "want", "looking for"],
}

def make_call(to_phone_number: str):
    try:
        print(f"Making call to {to_phone_number}")
        call = twilio_client.calls.create(
            to=to_phone_number,
            from_=os.getenv("TWILIO_PHONE_NUMBER"),  # Your Twilio number
            url=os.getenv("OUTGOING_CALL_URL")  # Your endpoint for handling call responses
        )
        return call.sid
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

def build_prompt(client_number, user_input):
    context = get_context(client_number)
    predefined_contexts = " ".join([PREDEFINED_CONTEXT[key] for key in context.get('voice', {}).keys()])
    prompt = f"{predefined_contexts} Current input: {user_input}."
    return prompt

def extract_information(user_input):
    extracted_info = {}
    for key, phrases in EXTRACTION_KEYWORDS.items():
        for phrase in phrases:
            if phrase in user_input.lower():
                extracted_info[key] = user_input
                break
    return extracted_info

def transcribe_audio(media_uri):
    job_name = "transcription_job"
    transcribe_client.start_transcription_job(
        TranscriptionJobName=job_name,
        Media={'MediaFileUri': media_uri},
        MediaFormat='wav',
        LanguageCode='en-US'
    )
    return transcribe_client.get_transcription_job(TranscriptionJobName=job_name)

def get_chatgpt_response(prompt):
    openai.api_key = OPENAI_API_KEY
    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": prompt}]
    )
    return response['choices'][0]['message']['content']

def synthesize_speech(text, voice_id='Joanna', rate='medium', pitch='medium', volume='medium'):
    response = polly_client.synthesize_speech(
        Text=text,
        OutputFormat='mp3',
        VoiceId=voice_id
    )
    return io.BytesIO(response['AudioStream'].read())

# Conversation context storage
conversation_context = {}

def update_context(client_number, user_input, gpt_response, voice_config=None):
    if client_number not in conversation_context:
        conversation_context[client_number] = {
            'history': [],
            'voice': voice_config or {}
        }
    
    conversation_context[client_number]['history'].append({
        "user": user_input,
        "gpt": gpt_response
    })

def get_context(client_number):
    return conversation_context.get(client_number, {'history': []})


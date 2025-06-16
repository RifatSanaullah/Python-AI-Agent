# app/config.py
from pydantic_settings import BaseSettings
import os
from dotenv import load_dotenv

load_dotenv()

class Settings(BaseSettings):
    database_url: str = os.getenv("DATABASE_URL")
    twilio_account_sid: str = os.getenv("TWILIO_ACCOUNT_SID")
    twilio_auth_token: str = os.getenv("TWILIO_AUTH_TOKEN")
    twilio_phone_number: str = os.getenv("TWILIO_PHONE_NUMBER")
    chatgpt_api_key: str = os.getenv("CHATGPT_API_KEY")
    aws_access_key_id: str = os.getenv("AWS_ACCESS_KEY_ID")
    aws_secret_access_key: str = os.getenv("AWS_SECRET_ACCESS_KEY")
    aws_region: str = os.getenv("AWS_REGION")
    aws_role_arn: str = os.getenv("AWS_ROLE_ARN")
    s3_bucket_name: str = os.getenv("S3_BUCKET_NAME", "ai-agent-boom")
    polly_voice_id: str = os.getenv("POLLY_VOICE_ID", "Joanna")
    domain: str = os.getenv("DOMAIN", "localhost")
    base_url: str = os.getenv("BASE_URL", "http://${domain}")
    ai_backend_url: str = os.getenv("AI_BACKEND_URL", "http://localhost:4000/v1")
    boom_backend_url: str = os.getenv("BOOM_BACKEND_URL", "http://localhost:3567")
    boom_number: str = os.getenv("BOOM_NUMBER", "+18774090666")
    deepgram_apikey: str = os.getenv("DEEPGRAM_API_KEY")
    playht_id: str = os.getenv("PLAY_HT_USER_ID")
    playht_apikey: str = os.getenv("PLAY_HT_API_KEY")
    elevenlabs_apikey: str = os.getenv("ELEVENLABS_API_KEY")
    elevenlabs_voice_id: str = os.getenv("ELEVENLABS_VOICE_ID", "8LVfoRdkh4zgjr8v5ObE") 
    tts_provider: str = os.getenv("TTS_PROVIDER", "deepgram") # or elevenlabs or playht
    nango_secret_key: str = os.getenv("NANGO_SECRET_KEY", "")
    nango_base_url: str = os.getenv("NANGO_BASE_URL", "https://api.nango.dev")
    cinc_client_id: str = os.getenv("CINC_CLIENT_ID", "09d1df90-5d42-48f8-9f34-5caf6c766873") # Updated
    cinc_client_secret: str = os.getenv("CINC_CLIENT_SECRET", "8f0bca42ac2140b583a5e4148e262ce2ba5ca348a0a348dcb862c2982c12bd7b") # Updated
    cinc_redirect_uri: str = os.getenv("CINC_REDIRECT_URI", "http://localhost:8000/cinc/callback") # Ensure this is the backend callback
    frontend_url: str = os.getenv("FRONTEND_URL", "http://localhost:3000") # Updated base frontend URL
    frontend_cinc_callback_path: str = os.getenv("FRONTEND_CINC_CALLBACK_PATH", "/dashboard/account/api-integration") # Corrected path

settings = Settings()

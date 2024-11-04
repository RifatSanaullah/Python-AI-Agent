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
    chatgpt_api_key: str = os.getenv("OPENAI_API_KEY")
    aws_access_key_id: str = os.getenv("AWS_ACCESS_KEY_ID")
    aws_secret_access_key: str = os.getenv("AWS_SECRET_ACCESS_KEY")
    aws_region: str = os.getenv("AWS_REGION")
    polly_voice_id: str = os.getenv("POLLY_VOICE_ID", "Joanna")
    base_url: str = os.getenv("BASE_URL", "http://localhost:8000")

settings = Settings()

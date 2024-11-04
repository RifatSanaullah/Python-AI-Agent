# app/services/polly_service.py
import boto3
import os
from app.config import settings

class PollyService:
    def __init__(self):
        print(settings)
        self.client = boto3.client(
            'polly',
            aws_access_key_id=settings.aws_access_key_id, #os.getenv("AWS_ACCESS_KEY_ID"),
            aws_secret_access_key=settings.aws_secret_access_key, #os.getenv("AWS_SECRET_ACCESS_KEY"),
            region_name=settings.aws_region #os.getenv("AWS_REGION")
        )

    def stream_text_to_speech(self, text: str):
        response = self.client.synthesize_speech(
            Text=text,
            OutputFormat='mp3',
            VoiceId=settings.polly_voice_id
        )
        return response['AudioStream']

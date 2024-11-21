import boto3
from app.config import settings
import audioop

class PollyService:
    def __init__(self):
        self.client = boto3.client(
            'polly',
            aws_access_key_id=settings.aws_access_key_id,
            aws_secret_access_key=settings.aws_secret_access_key,
            region_name=settings.aws_region
        )

    async def stream_text_to_speech(self, text: str):
        try:
            response = self.client.synthesize_speech(
                Text=text,
                OutputFormat='pcm',
                VoiceId=settings.polly_voice_id,
                SampleRate='8000',
                Engine='generative',
            )
            audio_bytes = response['AudioStream'].read()
            mulaw_audio_bytes = audioop.lin2ulaw(audio_bytes, 2)
            return mulaw_audio_bytes
        except self.client.exceptions.InvalidSsmlException as e:
            print(f"Invalid SSML request: {e}")
            raise
        except Exception as e:
            print(f"An error occurred: {e}")
            raise

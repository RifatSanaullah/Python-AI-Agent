import openai
from app.config import settings
import base64
from pydub import AudioSegment
import io

class ChatGPTAudioService:
    def __init__(self):
        openai.api_key = settings.chatgpt_api_key

    async def generate_response_from_audio(self, audio_bytes: bytes, knowledge_base: str = ""):
        audio_base64 = base64.b64encode(audio_bytes).decode('utf-8')
        response = openai.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": knowledge_base},
                {"role": "user", "content": audio_base64},
            ],
        )
        return response.choices[0].message.content

    async def transcribe_audio(self, audio_bytes: bytes):
        try:
            # Convert mulaw to wav
            audio = AudioSegment.from_file(io.BytesIO(audio_bytes), format="mulaw")
            wav_io = io.BytesIO()
            audio.export(wav_io, format="wav")
            wav_io.seek(0)

            response = openai.audio.transcriptions.create(
                model="whisper-1",
                file=wav_io,
                response_format="text"
            )
            return response['text']
        except FileNotFoundError as e:
            if 'ffprobe' in str(e) or 'ffmpeg' in str(e):
                raise RuntimeError("ffmpeg and ffprobe must be installed and available in your PATH.")
            else:
                raise e
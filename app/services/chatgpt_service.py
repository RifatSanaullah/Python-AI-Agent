# app/services/chatgpt_service.py
import openai
from app.config import settings

class ChatGPTService:
    def __init__(self):
        openai.api_key = settings.chatgpt_api_key

    async def generate_response(self, message: str, knowledge_base: str = ""):
        response = openai.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": knowledge_base},
                {"role": "user", "content": message},
            ],
        )
        return response.choices[0].message['content']

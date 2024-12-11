# app/services/chatgpt_service.py
import openai
from requests import Session
from app.config import settings
from app.services.knowledge_base_service import list_knowledge_entries

class ChatGPTService:
    def __init__(self):
        openai.api_key = settings.chatgpt_api_key

    async def generate_response(self, message: str, db: Session):
        knowledge = list_knowledge_entries(db)[0].answer
        response = openai.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "Keep your responses helpful and respectful and in under 2 senternces if possible."},
                {"role": "system", "content": knowledge},
                {"role": "user", "content": message},
            ],
        )
        return response.choices[0].message.content

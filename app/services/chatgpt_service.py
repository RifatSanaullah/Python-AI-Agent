# app/services/chatgpt_service.py
import openai
from requests import Session
from app.config import settings
from app.services.knowledge_base_service import list_knowledge_entries

class ChatGPTService:
    def __init__(self, db: Session):
        openai.api_key = settings.chatgpt_api_key
        self.knowledge = list_knowledge_entries(db)[0].answer

    async def generate_response(self, conversation_history):
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=conversation_history,
        )
        return response.choices[0].message.content

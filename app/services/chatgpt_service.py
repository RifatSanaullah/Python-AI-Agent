# app/services/chatgpt_service.py
import openai
from app.config import settings
from .knowledge_base_service import list_knowledge_entries

class ChatGPTService:
    def __init__(self):
        openai.api_key = settings.chatgpt_api_key

    async def generate_response(self, message: str):
        knowledge_base = list_knowledge_entries()
        knowledge_string = "Knowledge Base:\n"
        for knowledge in knowledge_base:
            knowledge_string += f"{knowledge['title']}: {knowledge['content']}\n"
        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": knowledge_string},
                {"role": "user", "content": message},
            ],
        )
        return response.choices[0].message['content']

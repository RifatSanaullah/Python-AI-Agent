
import openai
from app.config import settings

class OpenAiAdapter:
    def __init__(self, model = 'gpt-3.5-turbo'):
        openai.api_key = settings.chatgpt_api_key
        self.model = model

    async def generate_response(self, model, messages):
        if model:
            self.model = model
        response = openai.chat.completions.create(
            model=self.model,
            messages=messages,
            # stream=True  # Enable streaming
        )
        print("Assistant: ", end="", flush=True)  # Print the assistant's response incrementally
        assistant_reply = response.choices[0].message.content
        return assistant_reply
    


    

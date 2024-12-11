# app/services/chatgpt_service.py
import openai
from requests import Session
from app.config import settings
from app.services.knowledge_base_service import list_knowledge_entries

class ChatGPTService:
    def __init__(self, db: Session):
        openai.api_key = settings.chatgpt_api_key
        self.conversations = {}
        self.knowledge = list_knowledge_entries(db)[0].answer
        self.max_chunk_size = 200

    # Function to add messages to a conversation
    def add_message(self, conversation_id, role, content):
        if conversation_id not in self.conversations:
            print(f"Conversation ID {conversation_id} does not exist.")
            return
        
        self.conversations[conversation_id].append({"role": role, "content": content})

    def initial_message(self , conversation_id, knowledge_base: str = ""):
        self.conversations[conversation_id] = [
                {"role": "system", "content": "Keep your responses helpful and respectful and in under 2 senternces if possible."},
                {"role": "system", "content": knowledge_base},
        ]

    async def generate_response(self, conversation_id, message: str, synthesize_response):

        if conversation_id not in self.conversations:
            self.initial_message(conversation_id , self.knowledge)
        
        # Add user input to conversation history
        self.add_message(conversation_id, "user", message)
        response = openai.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=self.conversations[conversation_id],
            stream=True  # Enable streaming
        )
        print("Assistant: ", end="", flush=True)  # Print the assistant's response incrementally
        assistant_reply = ""

        # Process the streamed chunks
        for chunk in response:
            if chunk.choices and chunk.choices[0].delta:
                delta = chunk.choices[0].delta
                if delta.content:
                    val = delta.content
                    print(val, end="", flush=True)  # Display the streamed text
                    assistant_reply += val  # Save the full assistant response
                    if len(assistant_reply) > self.max_chunk_size:
                        await synthesize_response(assistant_reply)
                        assistant_reply=''
                    
        self.add_message(conversation_id, "assistant", assistant_reply)
        return assistant_reply
    
        # Function to close a conversation
    def close_conversation(self, conversation_id):
        if conversation_id in self.conversations:
            del self.conversations[conversation_id]
            print(f"Conversation ID {conversation_id} is now closed.")
        else:
            print(f"Conversation ID {conversation_id} does not exist.")

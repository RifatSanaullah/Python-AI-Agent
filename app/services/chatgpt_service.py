# app/services/chatgpt_service.py
import openai
from requests import Session
from app.config import settings

class ChatGPTService:
    def __init__(self, db: Session):
        openai.api_key = settings.chatgpt_api_key
        self.conversations = {}
        self.max_chunk_size = 200

    # Function to add messages to a conversation
    def add_message(self, conversation_id, role, content):
        if conversation_id not in self.conversations:
            print(f"Conversation ID {conversation_id} does not exist.")
            return
        
        self.conversations[conversation_id].append({"role": role, "content": content})

    def initial_message(self , conversation_id, knowledge_base):

        self.conversations[conversation_id] = [
                {"role": "system", "content": "Keep your responses helpful and respectful and in under 2 senternces if possible."},
                {"role": "system", "content": "This is a voice conversation, so keep it brief—don,t ramble!You need to take control of the conversation. Do a opening greeting also. Take initiative for the conversation and your directive. You are handling clients of the baby boomer generation. With that in mind you need to sound professional. Never mention you are an AI or Voice Assistant. Keep the responses small and encourage the client speech. Always refer to yourself using your name.."},
        ]

        if not knowledge_base:
            return
        
        for item in knowledge_base:
            if item['type'] != 'GREETINGS':
                self.conversations[conversation_id].append(
                    {"role": "system", "content": item['content']}
                )

    async def generate_response(self, conversation_id, message: str, synthesize_response, get_agent_knowledge):

        if conversation_id not in self.conversations:
            knowledge = await get_agent_knowledge(conversation_id)
            self.initial_message(conversation_id , knowledge)
        
        # Add user input to conversation history
        self.add_message(conversation_id, "user", message)
        response = openai.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=self.conversations[conversation_id],
            stream=True  # Enable streaming
        )
        print("Assistant: ", end="", flush=True)  # Print the assistant's response incrementally
        assistant_reply = ""
        chunk_reply = ""

        # Process the streamed chunks
        for chunk in response:
            if chunk.choices and chunk.choices[0].delta:
                delta = chunk.choices[0].delta
                if delta.content:
                    val = delta.content
                    print(val, end="", flush=True)  # Display the streamed text
                    assistant_reply += val  # Save the full assistant response
                    chunk_reply += val  # Save the full assistant response
                    if len(chunk_reply) > self.max_chunk_size:
                        await synthesize_response(chunk_reply, conversation_id)
                        chunk_reply=''
                    
        self.add_message(conversation_id, "assistant", assistant_reply)
        return assistant_reply
    
        # Function to close a conversation
    def close_conversation(self, conversation_id):
        if conversation_id in self.conversations:
            del self.conversations[conversation_id]
            print(f"Conversation ID {conversation_id} is now closed.")
        else:
            print(f"Conversation ID {conversation_id} does not exist.")

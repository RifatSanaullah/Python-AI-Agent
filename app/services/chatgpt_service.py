# app/services/chatgpt_service.py
import openai
from app.config import settings
# Import date class from datetime module
from datetime import date

import re

class StreamingChunker:
    def __init__(self, max_length=200, onTTS=None, conversation_id=None):
        self.buffer = ""  # Store incoming characters
        self.max_length = max_length
        self.send_to_tts= onTTS
        self.conversation_id= conversation_id

    async def add_stream_data(self, char):
        self.buffer = char  # Append incoming characters
        
        # Check if we have a complete sentence AND at least 200 chars
        if len(self.buffer) >= self.max_length:
            chunk, remaining = self._split_at_sentence()
            if chunk:
                chunk = self.filter_message(chunk)
                print("chunk : " ,chunk)
                # self.buffer = remaining  # Keep the leftover text for the next chunk
                await self.send_to_tts(chunk, self.conversation_id)  # Process the completed chunk
                await self.add_stream_data(remaining)

    async def flush(self):
        """Force send any remaining text when stream ends."""
        if self.buffer.strip():
            chunk = self.filter_message(self.buffer)
            print("chunk : ", chunk)
            await self.send_to_tts(chunk, self.conversation_id)
            self.buffer = ""

    def _split_at_sentence(self):
        """Find the nearest full sentence before max_length."""
        # sentences = re.split(r'(?<=[.!?])\s+', self.buffer)  # Split at sentence end
        sentences = re.findall(r'[^.!?]*[.!?]', self.buffer, re.DOTALL)
        chunk, remaining = "", ""

        for sentence in sentences:
            if len(chunk) + len(sentence) <= self.max_length:
                chunk += " " + sentence if chunk else sentence
            else:
                remaining = " ".join(sentences[sentences.index(sentence):])  # Save leftover
                break
        
        return chunk.strip(), remaining.strip()  # Return cleanly formatted chunks

    def filter_message(self, message):
        if 'End Call Message' in message or 'Routing Message' in message:
            message = message.replace('End Call Message', '')
            message = message.replace('Routing Message', '')
        return message
class ChatGPTService:
    def __init__(self):
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
                # {"role": "system", "content": "Keep your responses helpful and respectful and in under 2 sentences if possible."},
                # {"role": "system", "content": f"This is a voice conversation, so keep it brief — don,t ramble! You need to take control of the conversation. Do a opening greeting also. Take initiative for the conversation and your directive. You are handling clients of the baby boomer generation. With that in mind you need to sound professional. Never mention you are an AI or Voice Assistant or Virtual Assistant or Assistant. Always refer to yourself using your name: {knowledge_base['agentName']} and your gender is {knowledge_base['gender']}. Keep the responses small and encourage the client speech. -Be kind, funny, and a bit witty! Keep the conversation light. Use casual language like 'Umm...', 'Well...', 'I mean...'."},
                # # {"role": "system", "content": "Whenever you get any answer and if you left any query. Ask instantly don't wait for querying from user."},
                # # {"role": "system", "content": "Before Ending the call you have to reclarify all the information you gather with user"},
                # # {"role": "system", "content": f"Current Date is: {date.today()}. If you gather any input in tomorrow or yesterday then response any date information in this format : 01 january 1970 with the time and if input only time then use use the time with current date"},
                # {"role": "system", "content": "From the below questions data there will have a end call message. So you should finish the call when all the queries answered and deliver then end call message start with : End Call Message."},
        
        ]

        # if not knowledge_base:
        #     return
        
        # if knowledge_base['aiInstructions']:
        #     self.conversations[conversation_id].append(
        #             {"role": "system", "content": knowledge_base['aiInstructions']}
        #         )
            
        if not knowledge_base['knowledge']:
            return
        
        # self.conversations[conversation_id].append(
        #             {"role": "system", "content": "When the user asks about business or other information, respond only using the provided knowledge data and if the information is not available kindly notify the user. Do not ask for their details during this exchange. Once they have completed their query, you may resume asking for their details as needed."},
        # )
                        
        for item in knowledge_base['knowledge']:
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
            model="gpt-4-turbo",
            messages=self.conversations[conversation_id],
            # stream=True  # Enable streaming
        )
        print("Assistant: ", end="", flush=True)  # Print the assistant's response incrementally
        assistant_reply = ""
        chunk_reply = ""
        chunker = StreamingChunker(max_length=200, onTTS=synthesize_response, conversation_id=conversation_id)
        # Process the streamed chunks

        text = response.choices[0].message.content

        await chunker.add_stream_data(text)  # Simulating stream input

        # for chunk in response:
        #     if chunk.choices and chunk.choices[0].delta:
        #         delta = chunk.choices[0].delta
        #         if delta.content:
        #             val = delta.content
        #             print(val, end="", flush=True)  # Display the streamed text
        #             assistant_reply += val  # Save the full assistant response
        #             await chunker.add_stream_data(val)
        #             # chunk_reply += val  # Save the full assistant response
        #             # if len(chunk_reply) > self.max_chunk_size:
        #             #     chunk_reply = self.filter_message(chunk_reply)
        #             #     await synthesize_response(chunk_reply, conversation_id)
        #             #     chunk_reply=''
        await chunker.flush()
        # if chunk_reply and chunk_reply != '':
        #     chunk_reply = self.filter_message(chunk_reply)
        #     await synthesize_response(chunk_reply, conversation_id)
                    
        self.add_message(conversation_id, "assistant", assistant_reply)
        return assistant_reply
    
        # Function to close a conversation
    def close_conversation(self, conversation_id):
        if conversation_id in self.conversations:
            del self.conversations[conversation_id]
            print(f"Conversation ID {conversation_id} is now closed.")
        else:
            print(f"Conversation ID {conversation_id} does not exist.")
    

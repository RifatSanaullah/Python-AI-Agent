# app/services/chatgpt_service.py
import openai
from app.config import settings
# Import date class from datetime module
from datetime import date, datetime

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
        self.system_convo ={}
        self.convo_index = 0
    # Function to add messages to a conversation

    def json_serial(self, obj):
        """JSON serializer for objects not serializable by default json code"""

        if isinstance(obj, (datetime, date)):
            return obj.isoformat()
        raise TypeError ("Type %s not serializable" % type(obj))
    
    def add_message(self, conversation_id, role, content):
        if conversation_id not in self.conversations:
            print(f"Conversation ID {conversation_id} does not exist.")
            return
        
        self.conversations[conversation_id].append({"role": role, "content": content , "timestamp" : self.json_serial(datetime.now())})
        # Function to add messages to a conversation

    def add_system_message(self, conversation_id, role, content):
        if conversation_id not in self.system_convo:
            print(f"Conversation ID {conversation_id} does not exist.")
            return
        
        self.system_convo[conversation_id].append({"role": role, "content": content})

    def initial_message(self , conversations, conversation_id, knowledge_base):

        conversations[conversation_id] = [

                {"role": "system", "content": f"Always ask only one question at a time. After each response, follow up with a single question. For example, if you need contact information, ask for the name first, then phone number, then email—one at a time. Do not ask for multiple pieces of information or offer multiple options in one message. Always provide responses that are suitable for phone conversations. Avoid lengthy explanations, long lists, or complex details. Limit responses to key points. Keep responses under 3 sentences to ensure they are concise and easy to digest.Always refer to yourself using your name: {knowledge_base['agentName']} and your gender is {knowledge_base['gender']}"},
                 # {"role": "system", "content": "Whenever you get any answer and if you left any query. Ask instantly don't wait for querying from user."},
                # {"role": "system", "content": "Before Ending the call you have to reclarify all the information you gather with user"},
                # {"role": "system", "content": f"Current Date is: {date.today()}. If you gather any input in tomorrow or yesterday then response any date information in this format : 01 january 1970 with the time and if input only time then use use the time with current date"},
        ]

        if not knowledge_base:
            return
        
            
        if not knowledge_base['knowledge']:
            return
        
        # self.conversations[conversation_id].append(
        #             {"role": "system", "content": "When the user asks about business or other information, respond only using the provided knowledge data and if the information is not available kindly notify the user. Do not ask for their details during this exchange. Once they have completed their query, you may resume asking for their details as needed."},
        # )
                        
        for item in knowledge_base['knowledge']:
            if item['type'] != 'GREETINGS':
                conversations[conversation_id].append(
                    {"role": "system", "content": item['content']}
                )

        if knowledge_base['aiInstructions']:
            conversations[conversation_id].append(
                    {"role": "system", "content": knowledge_base['aiInstructions']}
                )

    async def process_initial_message(self, conversation_id, get_agent_knowledge):

        if conversation_id not in self.conversations:
            knowledge = await get_agent_knowledge(conversation_id)
            # self.initial_message(self.conversations, conversation_id, knowledge)
            self.initial_message(self.system_convo, conversation_id, knowledge)
            self.conversations[conversation_id] = []
            self.convo_index = len(self.system_convo[conversation_id])



    async def generate_response(self, conversation_id, message: str, synthesize_response):

        
        # Add user input to conversation history
        self.add_message(conversation_id, "user", message)


        self.add_system_message(conversation_id, "user", message)

        response = openai.chat.completions.create(
            model="gpt-4-turbo",
            messages=self.system_convo[conversation_id],
            # stream=True  # Enable streaming
        )
        print("Assistant: ", end="", flush=True)  # Print the assistant's response incrementally
        assistant_reply = ""
        chunk_reply = ""
        chunker = StreamingChunker(max_length=200, onTTS=synthesize_response, conversation_id=conversation_id)
        # Process the streamed chunks

        assistant_reply = response.choices[0].message.content

        await chunker.add_stream_data(assistant_reply)  # Simulating stream input

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
        self.add_system_message(conversation_id, "assistant", assistant_reply)


        if (conversation_id in self.system_convo and len(self.system_convo[conversation_id]) >= 6 + self.convo_index):

            allmessages = 'Get summary with every context of below conversations: '
            for index in range(self.convo_index, len(self.system_convo[conversation_id])) :
                item = self.system_convo[conversation_id][index]
                allmessages +=  f"{item['role']}:  {item['content']}\n\n"
            
            response = openai.chat.completions.create(
                model="gpt-4-turbo",
                messages=[{"role" : "user" , "content" : allmessages}],
            )
            del self.system_convo[conversation_id][self.convo_index: len(self.system_convo[conversation_id])]

            self.convo_index += 1
            summary = response.choices[0].message.content
            self.add_system_message(conversation_id, "assistant", summary)

        return assistant_reply
    
        # Function to close a conversation
    def close_conversation(self, conversation_id):
        self.convo_index = 0
        if conversation_id in self.conversations:
            del self.conversations[conversation_id]
            print(f"Conversation ID {conversation_id} is now closed.")
        else:
            print(f"Conversation ID {conversation_id} does not exist.")

        if conversation_id in self.system_convo:
            del self.system_convo[conversation_id]
            print(f"Conversation ID {conversation_id} is now closed.")
        else:
            print(f"Conversation ID {conversation_id} does not exist.")

    

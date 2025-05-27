# app/services/chatgpt_service.py
import openai
from app.config import settings
# Import date class from datetime module
from datetime import date, datetime
from app.services.nango_openai_service import NangoOpenAIService
from app.services.zoho_service import ZohoService
from app.services.hubspot_service import HubSpotService
from app.services.salesforce_service import SalesforceService
from app.services.calendly_service import CalendlyService
from app.services.google_calendar_service import GoogleCalendarService
from app.services.outlook_calendar_service import OutlookCalendarService
from typing import Dict, Any, List
from app.services.backend_service import BackendHandler

import re, json

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
    def __init__(self, integration_type: str = "zoho"):
        openai.api_key = settings.chatgpt_api_key
        self.conversations = {}
        self.integrations= {}
        self.max_chunk_size = 200
        self.system_convo = {}
        self.convo_index = 0
        self.nango_openai_service = NangoOpenAIService()
        self.zoho_service = ZohoService()
        self.hubspot_service = HubSpotService()
        self.salesforce_service = SalesforceService()
        self.calendly_service = CalendlyService()
        self.google_calendar_service = GoogleCalendarService()
        self.outlook_calendar_service = OutlookCalendarService()
        self.backend_service = BackendHandler()
                # Set the integration type
        # Initialize integration services and endpoints
        self.endpoints = {}
        self.method_mappings = {}
        
        # Initialize service-specific components based on integration type
        
    # Function to add messages to a conversation

    def _initialize_integration(self):
        """Initialize integration-specific settings and services"""
        # Initialize services based on integration type
        integration_type = self.integration_type.lower()
        
        # Currently supported integrations
        if integration_type == "zoho":
            service = ZohoService()
            self.endpoints[integration_type] = [
                "get-contacts",
                "get-contact-by-id",
                "get-accounts",
                "get-account-by-id",
                "get-leads",
                "get-lead-by-id",
                "get-deals",
                "get-deal-by-id",
                "get-products",
                "get-product-by-id",
                "get-users",
                "get-user-by-id"
            ]
            
            # Map endpoints to service methods
            self._map_service_methods(integration_type, service)

        elif integration_type == "hubspot":
            service = HubSpotService()
            self.endpoints[integration_type] = [
                "get-all-contacts",
                "get-contact-by-id",
                "get-recent-contacts",
                "get-all-companies",
                "get-company-by-id",
                "get-deals",
                "get-deal-by-id",
                "get-tickets",
                "get-ticket-by-id",
                "get-line-items",
                "get-line-item-by-id",
                "get-products",
                "get-product-by-id",
                "get-owners",
                "store-contacts",
                "get-owner-by-id"
            ]
            self._map_service_methods(integration_type, service)
            
        elif integration_type == "salesforce":
            service = SalesforceService()
            self.endpoints[integration_type] = [
                "get-accounts",
                "get-account-by-id",
                "get-contacts",
                "get-contact-by-id",
                "get-leads",
                "get-lead-by-id",
                "get-opportunities",
                "get-opportunity-by-id",
                "get-cases",
                "get-case-by-id",
                "get-products",
                "get-product-by-id",
                "get-users",
                "get-user-by-id",
                "get-campaigns",
                "get-campaign-by-id"
            ]
            self._map_service_methods(integration_type, service)
            
        elif integration_type == "calendly":
            service = CalendlyService()
            self.endpoints[integration_type] = [
                "users",
                "events",
            ]
            self._map_service_methods(integration_type, service)
        
        elif integration_type == "google-calendar":
            service = GoogleCalendarService()
            self.endpoints[integration_type] = [
                "events",
            ]
            self._map_service_methods(integration_type, service)
            
        elif integration_type == "outlook":
            service = OutlookCalendarService()
            self.endpoints[integration_type] = [
                "events",
            ]
            self._map_service_methods(integration_type, service)
    
        # Future integrations can be added here without changing the core logic
    
    def _map_service_methods(self, integration_type: str, service: Any):
        """Map service methods to endpoints dynamically
        
        Args:
            integration_type: The type of integration (e.g., 'zoho')
            service: The service instance to map methods from
        """
        # Initialize method mappings for this integration if not exists
        if integration_type not in self.method_mappings:
            self.method_mappings[integration_type] = {}
            
        # For each endpoint, find the corresponding method in the service
        for endpoint in self.endpoints.get(integration_type, []):
            # Convert endpoint name to method name (e.g., 'get-contacts' -> 'get_contacts')
            method_name = endpoint.replace('-', '_')
            
            # Check if the method exists in the service
            if hasattr(service, method_name):
                self.method_mappings[integration_type][endpoint] = getattr(service, method_name)
            else:
                print(f"Warning: Method {method_name} not found in {integration_type} service")

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
        # Initialize conversation with metadata
        if conversation_id not in conversations:
            conversations[conversation_id] = []
        
        # Initialize metadata if not exists
        if 'metadata' not in conversations:
            conversations['metadata'] = {}
        if conversation_id not in conversations['metadata']:
            conversations['metadata'][conversation_id] = {}

        conversations[conversation_id] = [

                {"role": "system", "content": f"Always ask only one question at a time. After each response, follow up with a single question. For example, if you need contact information, ask for the name first, then phone number, then email—one at a time. Do not ask for multiple pieces of information or offer multiple options in one message. Always provide responses that are suitable for phone conversations. Avoid lengthy explanations and special character (*), long lists, or complex details. Current Date is: {date.today()} if you have been asked for any appointment or booking dates do not give the dates which has already been passed. Limit responses to key points and do not rush to complete the conversation. Keep responses under 3 sentences to ensure they are concise and easy to digest.Always refer to yourself using your name: {knowledge_base['agentName']} and your gender is {knowledge_base['gender']}"},
                 # {"role": "system", "content": "Whenever you get any answer and if you left any query. Ask instantly don't wait for querying from user."},
                # {"role": "system", "content": "Before Ending the call you have to reclarify all the information you gather with user"},
                # {"role": "system", "content": f"Current Date is: {date.today()}. If you gather any input in tomorrow or yesterday then response any date information in this format : 01 january 1970 with the time and if input only time then use use the time with current date"},
        ]
        connection_id = None
        integration = None
        # Check if this conversation has a Zoho or HubSpot connection ID stored in metadata
        if 'integration' in knowledge_base and knowledge_base['integration']['zoho_connection_id'] is not None:
            connection_id = knowledge_base['integration']['zoho_connection_id']
            integration = 'Zoho'
        
        if 'integration' in knowledge_base and knowledge_base['integration']['hubspot_connection_id'] is not None:
            integration = 'HubSpot'
            connection_id = knowledge_base['integration']['hubspot_connection_id']
                
        if 'integration' in knowledge_base and knowledge_base['integration']['salesforce_connection_id'] is not None:
            integration = 'Salesforce'
            connection_id = knowledge_base['integration']['salesforce_connection_id']
            
        if 'integration' in knowledge_base and knowledge_base['integration']['calendly_connection_id'] is not None:
            integration = 'Calendly'
            connection_id = knowledge_base['integration']['calendly_connection_id']
            
        if 'integration' in knowledge_base and knowledge_base['integration']['google_calendar_connection_id'] is not None:
            integration = 'Google Calendar'
            connection_id = knowledge_base['integration']['google_calendar_connection_id']
            
        if 'integration' in knowledge_base and knowledge_base['integration']['outlook_connection_id'] is not None:
            integration = 'Outlook Calendar'
            connection_id = knowledge_base['integration']['outlook_connection_id']

        if connection_id is not None:
            conversations[conversation_id].append(
                {"role": "system", "content": f"You have access to {integration} CRM data. When the caller mentions a name, company, or other identifying information, you can use this to provide personalized responses based on their CRM data. If they ask about their account, deals, or other business information, you can reference this data to provide accurate answers.Use {integration} CRM data with connection ID {connection_id} if the bellow message is relevent than use the required tool call otherwise just response the user message without using tool call and response the user message normally:"}
            )

        if not knowledge_base:
            return
        
            
        if not knowledge_base['knowledge']:
            return
        
        # self.conversations[conversation_id].append(
        #             {"role": "system", "content": "When the user asks about business or other information, respond only using the provided knowledge data and if the information is not available kindly notify the user. Do not ask for their details during this exchange. Once they have completed their query, you may resume asking for their details as needed."},
        # )
   
        for item in knowledge_base['knowledge']:
                if item['type'] != 'GREETINGS':
                    content = self.resolve_prompt(item['content'], knowledge_base['new_knowledge'])
                    print(f"Adding system message: {content}")
                    conversations[conversation_id].append(
                        {"role": "system", "content": content}
                    )

        if knowledge_base['aiInstructions']:
            conversations[conversation_id].append(
                    {"role": "system", "content": knowledge_base['aiInstructions']}
                )
    def get_senior_living_knowledge(self):
        return f"""You are the AI receptionist for BoomersHub. This caller is already in the CRM. Greet them by name and ask how you can assist.
                    Call Flow:
                        1. Greet & Ask Purpose
                            - Address the caller by name.
                            - Ask how you can help today.
                        2. If Caller Requests Info:
                            - If you know the answer: Provide it clearly, referring to past call summaries if needed. Then ask if they need anything else.
                            - If you don't know: Let them know a human advisor will follow up within 24 hours. Flag for escalation.
                        3. If Caller Wants to Update Info:
                            - Ask what details they want to change.
                            - Make the updates and confirm them.
                            - If no further help is needed, politely end the call.
                    Rules:
                        Never re-ask existing info unless confirming.
                        Be concise, warm, and professional.
                        Escalate only when necessary.
                        Always maintain control of the conversation.
                """
    def resolve_prompt(self, prompt_from_frontend: str, is_existing: bool) -> str:
        if is_existing:
            # Remove <if new>...</if> block
            prompt = re.sub(r'<if new>[\s\S]*?</if>', '', prompt_from_frontend, flags=re.IGNORECASE)
            # Extract and keep <if existing>...</if> block content
            prompt = re.sub(r'<if existing>([\s\S]*?)</if>', r'\1', prompt, flags=re.IGNORECASE)
        else:
            # Remove <if existing>...</if> block
            prompt = re.sub(r'<if existing>[\s\S]*?</if>', '', prompt_from_frontend, flags=re.IGNORECASE)
            # Extract and keep <if new>...</if> block content
            prompt = re.sub(r'<if new>([\s\S]*?)</if>', r'\1', prompt, flags=re.IGNORECASE)

        return prompt.strip()
    async def process_initial_message(self, conversation_id, get_agent_knowledge):

        if conversation_id not in self.conversations:
            knowledge = await get_agent_knowledge(conversation_id)
            # self.initial_message(self.conversations, conversation_id, knowledge)
            self.initial_message(self.system_convo, conversation_id, knowledge)
            self.conversations[conversation_id] = []
            self.convo_index = len(self.system_convo[conversation_id])
            self.integrations[conversation_id] = {
                "hubspot_connection_id": None,
                "zoho_connection_id": None,
                "salesforce_connection_id": None,
                "calendly_connection_id": None,
                "google_calendar_connection_id": None,
                "outlook_connection_id": None
            }
            # Check if this conversation has a CRM connection ID in the database
            try:
                if knowledge['integrations']:
                    self.integrations[conversation_id] = knowledge['integrations']
            except Exception as e:
                print(f"Error retrieving CRM connection IDs from database: {str(e)}")
            

                
    def _build_tool_schemas(self) -> List[Dict[str, Any]]:
        """Build OpenAI tool schemas dynamically based on the integration type"""
        schemas = []
        
        # Get endpoints for the current integration type
        integration_type = self.integration_type.lower()
        integration_endpoints = self.endpoints.get(integration_type, [])
        
        for endpoint in integration_endpoints:
            # Create a descriptive name for the endpoint
            entity_type = endpoint.split('-by-id')[0] if '-by-id' in endpoint else endpoint.split('-')[1] if '-' in endpoint else endpoint
            
            schema = {
                "type": "function",
                "function": {
                    "name": endpoint.replace("-", "_"),
                    "description": f"Call the Nango {integration_type} endpoint `{endpoint}`.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "connection_id": {
                                "type": "string",
                                "description": f"The Nango connection ID for the {integration_type} integration"
                            }
                        },
                        "required": ["connection_id"]
                    }
                }
            }
            
            # Add ID parameter for endpoints that require it
            if "-by-id" in endpoint:
                schema["function"]["parameters"]["properties"]["id"] = {
                    "type": "string",
                    "description": f"The ID of the {endpoint.split('-by-id')[0]} to retrieve"
                }
                schema["function"]["parameters"]["required"].append("id")
            
            schemas.append(schema)
        
        return schemas
      
    async def run_chat_with_tools(self, messages) -> Dict[str, Any]:
        response = openai.chat.completions.create(
            model="gpt-4-turbo",
            messages=messages,
            tools=self._build_tool_schemas(),
            tool_choice="auto"
        )
        return response
    async def run_chat_without_tools(self, messages) -> Dict[str, Any]:
        response = openai.chat.completions.create(
            model="gpt-4-turbo",
            messages=messages,
        )
        return response

    async def process_conversation(self, user_message: str) -> str:
            """Process a conversation with the user, handling any tool calls dynamically"""
            messages = [{"role": "user", "content": user_message}]
            initial_response = await self.run_chat_with_tools(messages)
            choice = initial_response.choices[0]
            
            if choice.finish_reason == "tool_calls":
                messages = [{"role": "user", "content": user_message}, choice.message]
                
                for tool_call in choice.message.tool_calls:
                    tool_output = await self.handle_tool_call(tool_call)
                    
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "name": tool_call.function.name,
                        "content": json.dumps(tool_output)
                    })
                
                followup = openai.chat.completions.create(
                    model="gpt-4-turbo",
                    messages=messages
                )
                
                return followup.choices[0].message.content
            else:
                return choice.message.content
            
    async def process_conversation_with_tool(self, conversation_id, connection_id, messages: str , integration: str) -> str:
        assistant_reply = ''
        try:
            # Create a modified message that includes context about available Zoho data
            # enhanced_message = f"The following is a user message in a phone conversation. Use {integration} CRM data with connection ID {connection_id} if the bellow message is relevent than use the required tool call otherwise just response the user message without using tool call and response the user message normally: {user_message}"
            
            # Get enhanced response from NangoOpenAIService
            enhanced_response = await self.process_conversation(self.system_convo[conversation_id])
            
            # Use the enhanced response
            assistant_reply = enhanced_response
            print(f"Using {integration}-enhanced response")
        except Exception as e:
            print(f"Error using {integration} integration: {str(e)}")
        
            response = openai.chat.completions.create(
                model="gpt-4-turbo",
                messages=self.system_convo[conversation_id]
            )
            assistant_reply = response.choices[0].message.content
        return assistant_reply
            
    async def generate_response(self, conversation_id, message: str, synthesize_response):

        
        # Add user input to conversation history
        self.add_message(conversation_id, "user", message)
        self.add_system_message(conversation_id, "user", message)
        
        # Check if this conversation has a Zoho or HubSpot connection ID

        assistant_reply = ''
        # Prioritize HubSpot if both are available, or use whichever is available
        # if self.integrations[conversation_id]['hubspot_connection_id']:
        #     # Use NangoOpenAIService to enhance the response with HubSpot data
        #     self.integration_type = 'hubspot'
        #     self._initialize_integration()
        #     assistant_reply = await self.process_conversation_with_tool(conversation_id, self.integrations[conversation_id]['hubspot_connection_id'], self.system_convo[conversation_id], "HubSpot")

        # # Check if this conversation has a Zoho connection ID
        # elif self.integrations[conversation_id]['salesforce_connection_id']:
        #     # Use NangoOpenAIService to enhance the response with Zoho data
        #     self.integration_type = 'salesforce'
        #     self._initialize_integration()
        #     assistant_reply = await self.process_conversation_with_tool(conversation_id, self.integrations[conversation_id]['salesforce_connection_id'], self.system_convo[conversation_id], "Salesforce")
        
        # elif self.integrations[conversation_id]['zoho_connection_id']:
        #     # Use NangoOpenAIService to enhance the response with Zoho data
        #     self.integration_type = 'zoho'
        #     self._initialize_integration()
        #     assistant_reply = await self.process_conversation_with_tool(conversation_id, self.integrations[conversation_id]['zoho_connection_id'], self.system_convo[conversation_id], "Zoho")
        
        # else:
            # Standard response without CRM integration
        response = openai.chat.completions.create(
            model="gpt-4-turbo",
            messages=self.system_convo[conversation_id]
        )
        print("Assistant: ", end="", flush=True)  # Print the assistant's response incrementally
        assistant_reply = response.choices[0].message.content
    
        # Process the response for speech synthesis
        assistant_reply = assistant_reply.replace('*', '')
        chunk_reply = ""
        chunker = StreamingChunker(max_length=200, onTTS=synthesize_response, conversation_id=conversation_id)
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

            allmessages = 'Give me a summary with every context of below conversations: '
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
            self.add_system_message(conversation_id, "system", summary)

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
            
        # Clean up Zoho connection if it exists in metadata
        if 'metadata' in self.system_convo and conversation_id in self.system_convo['metadata']:
            del self.system_convo['metadata'][conversation_id]
            print(f"Zoho connection for conversation ID {conversation_id} removed from metadata.")
    


    async def get_nango_session_token(self, user_id, allowed_integrations=None):
        """Get a Nango session token for the frontend to use when connecting to third-party services"""
        if allowed_integrations is None:
            # Default to both Zoho and HubSpot if not specified
            allowed_integrations = await self.nango_openai_service.get_available_integrations()
        
        try:
            # Use the NangoOpenAIService to get a session token
            session_data = await self.nango_openai_service.get_session_token(
                user_id=user_id,
                allowed_integrations=allowed_integrations
            )
            
            print(f"Successfully retrieved Nango session token for user {user_id}")
            return session_data
        except Exception as e:
            print(f"Error getting Nango session token: {str(e)}")
            raise

    async def handle_tool_call(self, tool_call: Any) -> Dict[str, Any]:
            """Handle tool calls dynamically based on the integration type"""
            tool_name = tool_call.function.name.replace("_", "-")
            arguments = json.loads(tool_call.function.arguments)
            connection_id = arguments.get("connection_id")
            
            if not connection_id:
                raise ValueError(f"Missing 'connection_id' parameter for {tool_name}")
            
            # Determine which integration this tool belongs to
            integration_type = self.integration_type.lower()  # Default to current integration
            
            # Find the integration that has this tool
            for integ_type, endpoints in self.endpoints.items():
                if tool_name in endpoints:
                    integration_type = integ_type
                    break
            
            # Get the method mapping for the identified integration
            if integration_type not in self.method_mappings or tool_name not in self.method_mappings[integration_type]:
                raise ValueError(f"Unknown tool name: {tool_name} for integration: {integration_type}")
            
            method = self.method_mappings[integration_type][tool_name]
            
            # Handle methods that require an ID parameter
            if "-by-id" in tool_name:
                entity_id = arguments.get("id")
                if not entity_id:
                    raise ValueError(f"Missing 'id' parameter for {tool_name}")
                return await method(connection_id, entity_id)
            else:
                # Pass all other parameters except connection_id
                params = {k: v for k, v in arguments.items() if k != "connection_id"}
                return await method(connection_id, params if params else None)
    
            
    async def get_summary(self, response_format, conversations):
            summarize_prompt = {
                    "role": "user",
                    "content": f"""
                From the above conversation history, extract and return the following information in JSON format using the structure below. If any fields are not available in the conversation, leave them as empty strings (""). All date/time values should be formatted as JavaScript Date objects.
                Response Format:
                {json.dumps(response_format, indent=2)}
                Return only this structured JSON based on the conversation. If no data is found for a section, return that section with all fields as empty strings. :
                """
            }
            conversations.insert(0, summarize_prompt)
            result = await self.run_chat_without_tools(conversations)
            summary = result.choices[0].message.content
            summary = json.loads(summary)
            return summary







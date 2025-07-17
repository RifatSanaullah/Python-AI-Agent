# app/services/chatgpt_service.py

# app/services/chatgpt_service.py
import openai, asyncio
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
import html
import re, json, threading, queue
# import app.adapters.openai_adapter as OpenAiAdapter
class AIService:
    def __init__(self, integration_type: str = "zoho"):
        openai.api_key = settings.chatgpt_api_key
        self.conversations = {}
        self.integrations= {}
        self.max_chunk_size = 40
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
        # self.openai_adapter = OpenAiAdapter()

        # Initialize integration services and endpoints
        self.endpoints = {}
        self.method_mappings = {}
        self.summary_queue = queue.Queue()
        self.ai_interrupt = {}
        self.current_chunk = {}
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

                {"role": "system", "content": f"Always ask only one question at a time. After each response, follow up with a single question. For example, if you need contact information, ask for the name first, then phone number, then email—one at a time. Do not ask for multiple pieces of information or offer multiple options in one message. Always provide responses that are suitable for phone conversations. Avoid lengthy explanations and special character (*), long lists, or complex details. Current Date is: {date.today()} if you have been asked for any appointment or booking dates do not give the dates which has already been passed. Limit responses to key points and do not rush to complete the conversation. Keep responses under 3 sentences to ensure they are concise and easy to digest."},
                # {"role": "system", "content": self.generate_emotion_tag_prompt(date.today().isoformat())},
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
                    # print(f"Adding system message: {content}")
                    conversations[conversation_id].append(
                        {"role": "system", "content": content}
                    )

        if knowledge_base['aiInstructions']:
            conversations[conversation_id].append(
                    {"role": "system", "content": knowledge_base['aiInstructions']}
                )

    def resolve_prompt(self, prompt_from_frontend: str, is_existing: bool) -> str:
        # Step 1: Decode HTML entities
        prompt = html.unescape(prompt_from_frontend)

        # Step 2: Replace conditional blocks based on `is_existing`
        if is_existing:
            prompt = re.sub(r'<if new>[\s\S]*?</if>', '', prompt, flags=re.IGNORECASE)
            prompt = re.sub(r'<if existing>([\s\S]*?)</if>', r'\1', prompt, flags=re.IGNORECASE)
        else:
            prompt = re.sub(r'<if existing>[\s\S]*?</if>', '', prompt, flags=re.IGNORECASE)
            prompt = re.sub(r'<if new>([\s\S]*?)</if>', r'\1', prompt, flags=re.IGNORECASE)

        return prompt.strip()
    async def process_initial_message(self, conversation_id, get_agent_knowledge):

        if conversation_id not in self.conversations:
            knowledge = await get_agent_knowledge(conversation_id)
            # self.initial_message(self.conversations, conversation_id, knowledge)
            self.initial_message(self.system_convo, conversation_id, knowledge)
            # self.add_system_message(conversation_id, "system" , self.generate_emotion_tag_prompt())

            self.conversations[conversation_id] = []
            self.ai_interrupt[conversation_id] = {}
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
            model="gpt-4.1",
            messages=messages,
        )
        return response.choices[0].message.content

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
                model="gpt-4.1",
                messages=self.system_convo[conversation_id]
            )
            assistant_reply = response.choices[0].message.content
        return assistant_reply
    
    def update_interrupt_status(self, conversation_id, status: bool):
        """Update the AI interrupt status for a conversation"""
        if conversation_id not in self.current_chunk:
            self.current_chunk[conversation_id] = ""
        else:
            if conversation_id not in self.ai_interrupt:
                self.ai_interrupt[conversation_id][self.current_chunk[conversation_id]] = {}
            if self.ai_interrupt[conversation_id][self.current_chunk[conversation_id]] is not True:
                self.ai_interrupt[conversation_id][self.current_chunk[conversation_id]] = status

    def update_interrupt_details(self, conversation_id, chunk_id):
        """Update the AI interrupt status for a conversation"""
        self.current_chunk[conversation_id]= chunk_id
        if conversation_id not in self.ai_interrupt:
            self.ai_interrupt[conversation_id]= {}
        if chunk_id not in self.ai_interrupt:
            self.ai_interrupt[conversation_id][chunk_id]= False
        return
        
    def get_interrupt_status(self, conversation_id):
        if self.current_chunk and self.ai_interrupt and  conversation_id in self.ai_interrupt and conversation_id in self.current_chunk:
            return self.ai_interrupt[conversation_id][self.current_chunk[conversation_id]]
        else:
            return False
    def generate_emotion_tag_prompt(self, user_input):
                    return f"""
            You are a conversational voice assistant that replies with natural speech patterns.

            Respond to the user's question in a way that sounds like it's being spoken out loud.

            Use:
            - Dashes (— or -) for short pauses
            - Ellipses (…) for hesitations or trailing thoughts

            Keep it casual, emotionally expressive, and human-like.

            User: "{user_input}"
            Assistant:
"""
    async def generate_response(self, conversation_id, message: str, synthesize_response,ai_client, flush_ws, streamingResponse):

        
        # Add user input to conversation history
        self.add_message(conversation_id, "user", message)

        newPrompt = [
            {
                "role" : "system",
                "content" : "You respond like a natural human voice, using pauses and hesitations."
            },
            {
                "role" : "user",
                "content" : self.generate_emotion_tag_prompt(message)
            }
        ]
        # # self.add_system_message(conversation_id, "system", f"""
        # #             You will respond to the user's question in SSML format with emotional expression.
        # #             Rules:
        # #             - Output MUST be wrapped in <speak>...</speak>.
        # #             - Detect the emotion (happy, sad, surprised, calm, etc.).
        # #             - Use <prosody>, <emphasis>, and <break> tags.
        # #             - Don't explain anything, just return the SSML.
        # #             - Keep it short and emotionally expressive.
        # # """)
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
        if ai_client['name'] == 'OpenAI':
            response = openai.chat.completions.create(
                model=ai_client['model'],
                messages=self.system_convo[conversation_id] + newPrompt,
                stream=True,
                max_tokens=150,
            )
            self.add_system_message(conversation_id, "user", message)

            # print("Assistant: ", end="", flush=True)  # Print the assistant's response incrementally
            # assistant_reply = response.choices[0].message.content
        
            # Process the response for speech synthesis
            # assistant_reply = assistant_reply.replace('*', '')
            chunk_reply = ""
            # chunker = StreamingChunker(max_length=50, onTTS=synthesize_response, conversation_id=conversation_id, flush_ws=flush_ws)
            # await chunker.add_stream_data(assistant_reply)  # Simulating stream input
            end_call_prefix = "End Call Message"
            prefix_buffer = ""
            post_prefix_mode = False
            post_prefix_text = ""
            for chunk in response:
                self.update_interrupt_details(conversation_id, chunk.id)
                if self.ai_interrupt[conversation_id][chunk.id] is True:
                    print("AI interrupted, stopping response generation.")
                    break
                if chunk.choices and chunk.choices[0].delta:
                    delta = chunk.choices[0].delta
                    if delta.content:
                        val = delta.content
                        chunk_reply += val  # Save the full assistant response

                        # print(val, end="", flush=True)  # Display the streamed text
                        assistant_reply += val  # Save the full assistant response
                        if streamingResponse:
                            if not post_prefix_mode:
                                # Build up prefix buffer
                                prefix_buffer += val

                                if end_call_prefix in prefix_buffer:
                                    post_prefix_mode = True
                                    # Split at prefix
                                    post_prefix_text = prefix_buffer.split(end_call_prefix, 1)[1]
                                    if post_prefix_text.strip() and self.ai_interrupt[conversation_id][chunk.id] is not True:
                                        await synthesize_response(post_prefix_text, conversation_id)
                                elif not end_call_prefix.startswith(prefix_buffer) and self.ai_interrupt[conversation_id][chunk.id] is not True:
                                    # Prefix was never part of stream, flush buffer to TTS
                                    await synthesize_response(prefix_buffer, conversation_id)

                                    prefix_buffer = ""
                            elif self.ai_interrupt[conversation_id][chunk.id] is not True:
                                    await synthesize_response(val, conversation_id)                 

                        # await chunker.add_stream_data(val)

            # await chunker.flush()
            if not streamingResponse:
                await synthesize_response(chunk_reply, conversation_id)
            else:
                await flush_ws()
            # if chunk_reply and chunk_reply != '':
            #     chunk_reply = chunker.filter_message(chunk_reply)
            #     await synthesize_response(chunk_reply, conversation_id)

                
                    
        self.add_message(conversation_id, "assistant", assistant_reply)
        self.add_system_message(conversation_id, "assistant", assistant_reply)
        # if self.should_summarize(conversation_id):
        #     task = self.running_tasks.get(conversation_id)

        #     print("task started")
        #     if not task or task.done():
        #         print("task done")
        #         new_task = asyncio.create_task(self._run_safely(
        #             self.generate_summary_in_background(conversation_id)
        #         ))
        #         self.running_tasks[conversation_id] = new_task
        #     else:
        #         print("task pending")

        return assistant_reply

    def should_summarize(self, conversation_id):
        if (conversation_id in self.system_convo and len(self.system_convo[conversation_id]) >= 6 + self.convo_index):
            return True
        else: 
            return False

    async def _run_safely(self, coro):
        try:
            await coro
        except asyncio.CancelledError:
            print("Summary task was cancelled.")
        except Exception as e:
            print(f"[Async Summary Error] {e}")
    
        # Function to close a conversation
    async def generate_summary_in_background(self, conversation_id):
        try:
            if (conversation_id in self.system_convo and len(self.system_convo[conversation_id]) >= 6 + self.convo_index):

                allmessages = 'Give me a summary with every context of below conversations: '
                for index in range(self.convo_index, len(self.system_convo[conversation_id])) :
                    item = self.system_convo[conversation_id][index]
                    allmessages +=  f"{item['role']}:  {item['content']}\n\n"
                
                response = openai.chat.completions.create(
                    model="gpt-4.1",
                    messages=[{"role" : "user" , "content" : allmessages}],
                )
                del self.system_convo[conversation_id][self.convo_index: len(self.system_convo[conversation_id])]

                self.convo_index += 1
                summary = response.choices[0].message.content
                self.add_system_message(conversation_id, "system", summary)
        except Exception as e:
            print(f"[Summary Generation Error] {e}")

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
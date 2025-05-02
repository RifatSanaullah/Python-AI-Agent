import json
import openai
from typing import Dict, Any, List, Optional, Callable
from app.config import settings
from app.services.nango_service import NangoService
from app.services.zoho_service import ZohoService

class NangoOpenAIService:
    def __init__(self, integration_type: str = "zoho"):
        self.nango_service = NangoService()
        self.openai_api_key = settings.chatgpt_api_key
        openai.api_key = self.openai_api_key
        self.openai_model = "gpt-3.5-turbo-0613"  # Default model, can be configured
        
        # Set the integration type
        self.integration_type = integration_type
        
        # Initialize integration services and endpoints
        self.endpoints = {}
        self.method_mappings = {}
        
        # Initialize service-specific components based on integration type
        self._initialize_integration()
        
        # Build tool schemas for OpenAI
        self.tool_schemas = self._build_tool_schemas()
    
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
    
    async def run_chat_with_tools(self, user_message: str) -> Dict[str, Any]:
        messages = [{"role": "user", "content": user_message}]
        response = openai.ChatCompletion.create(
            model=self.openai_model,
            messages=messages,
            tools=self.tool_schemas,
            tool_choice="auto"
        )
        return response
    
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
    
    async def process_conversation(self, user_message: str) -> str:
        """Process a conversation with the user, handling any tool calls dynamically"""
        initial_response = await self.run_chat_with_tools(user_message)
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
            
            followup = openai.ChatCompletion.create(
                model=self.openai_model,
                messages=messages
            )
            
            return followup.choices[0].message.content
        else:
            return choice.message.content
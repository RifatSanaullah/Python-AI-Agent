import json
import openai
from typing import Dict, Any, List, Optional
from app.config import settings
from app.services.nango_service import NangoService

class NangoOpenAIService:
    def __init__(self):
        self.nango_service = NangoService()
        self.openai_api_key = settings.chatgpt_api_key
        openai.api_key = self.openai_api_key
        
        # Define the available Zoho endpoints
        self.zoho_endpoints = [
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
        
        # Build tool schemas for OpenAI
        self.tool_schemas = self._build_tool_schemas()
    
    def _build_tool_schemas(self) -> List[Dict[str, Any]]:
        schemas = []
        for endpoint in self.zoho_endpoints:
            schema = {
                "type": "function",
                "function": {
                    "name": endpoint.replace("-", "_"),
                    "description": f"Call the Nango Zoho endpoint `{endpoint}`.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "connection_id": {
                                "type": "string",
                                "description": "The Nango connection ID for the Zoho integration"
                            }
                        },
                        "required": ["connection_id"]
                    }
                }
            }
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
        
        tool_name = tool_call.function.name.replace("_", "-")
        arguments = json.loads(tool_call.function.arguments)
        connection_id = arguments.get("connection_id")
        
        # Map the tool name to the corresponding method in NangoService
        method_mapping = {
            "get-contacts": self.nango_service.get_zoho_contacts,
            "get-contact-by-id": self.nango_service.get_zoho_contact_by_id,
            "get-accounts": self.nango_service.get_zoho_accounts,
            "get-account-by-id": self.nango_service.get_zoho_account_by_id,
            "get-leads": self.nango_service.get_zoho_leads,
            "get-lead-by-id": self.nango_service.get_zoho_lead_by_id,
            "get-deals": self.nango_service.get_zoho_deals,
            "get-deal-by-id": self.nango_service.get_zoho_deal_by_id,
            "get-products": self.nango_service.get_zoho_products,
            "get-product-by-id": self.nango_service.get_zoho_product_by_id,
            "get-users": self.nango_service.get_zoho_users,
            "get-user-by-id": self.nango_service.get_zoho_user_by_id
        }
        
        if tool_name not in method_mapping:
            raise ValueError(f"Unknown tool name: {tool_name}")
        
        method = method_mapping[tool_name]
        
        # Handle methods that require an ID parameter
        if "-by-id" in tool_name:
            entity_id = arguments.get("id")
            if not entity_id:
                raise ValueError(f"Missing 'id' parameter for {tool_name}")
            return await method(connection_id, entity_id)
        else:
            params = {k: v for k, v in arguments.items() if k != "connection_id"}
            return await method(connection_id, params if params else None)
    
    async def process_conversation(self, user_message: str) -> str:
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
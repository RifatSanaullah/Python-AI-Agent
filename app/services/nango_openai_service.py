import json
import openai
from typing import Dict, Any, List, Optional, Callable
from app.config import settings
from app.services.nango_service import NangoService
from app.services.zoho_service import ZohoService
from app.services.hubspot_service import HubSpotService
from app.services.salesforce_service import SalesforceService
import logging
from typing import List, Optional

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("nango_openai_service")

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
    
    def _map_service_methods(self, integration_type: str, service: Any):
       
        # Initialize method mappings for this integration if not exists
        if integration_type not in self.method_mappings:
            self.method_mappings[integration_type] = {}
            
        
        for endpoint in self.endpoints.get(integration_type, []):
            
            method_name = endpoint.replace('-', '_')
            
            
            if hasattr(service, method_name):
                self.method_mappings[integration_type][endpoint] = getattr(service, method_name)
            else:
                print(f"Warning: Method {method_name} not found in {integration_type} service")
    
    def _build_tool_schemas(self) -> List[Dict[str, Any]]:
        schemas = []
        
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
        
    
        integration_type = self.integration_type.lower()  
        
        
        for integ_type, endpoints in self.endpoints.items():
            if tool_name in endpoints:
                integration_type = integ_type
                break
        
        
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
    
    async def get_session_token(self, user_id: str, allowed_integrations: List[str], 
                               user_email: Optional[str] = None, 
                               user_display_name: Optional[str] = None,
                               org_id: Optional[str] = None,
                               org_display_name: Optional[str] = None) -> Dict[str, Any]:
        """
        Get a Nango session token for the frontend to use when connecting to third-party services.
        
        Args:
            user_id: Unique identifier for the user
            allowed_integrations: List of integration IDs the user is allowed to connect to
            user_email: Optional email of the user
            user_display_name: Optional display name of the user
            org_id: Optional organization ID
            org_display_name: Optional organization display name
            
        Returns:
            Dictionary containing the session token
        """

        print(f"Getting Nango session token for user {user_id} with allowed integrations: {allowed_integrations}")
        try:
            # Use the NangoService to create a connect session and get a token
            session_data = await self.nango_service.create_connect_session(
                end_user_id=user_id,
                allowed_integrations=allowed_integrations,
                end_user_email=user_email,
                end_user_display_name=user_display_name,
                org_id=org_id,
                org_display_name=org_display_name
            )
            
            logger.info(f"Successfully retrieved Nango session token for user {user_id}")
            return session_data
        except Exception as e:
            logger.error(f"Error getting Nango session token: {str(e)}")
            raise
    
    async def get_available_integrations(self) -> List[str]:
        """
        Get a list of available integrations based on the current configuration.
        Currently returns hardcoded values for Zoho, HubSpot, and Salesforce.
        
        Returns:
            List of integration IDs
        """
        # In a real implementation, this might fetch from Nango API or configuration
        # For now, we'll return the hardcoded values for Zoho, HubSpot, and Salesforce
        return ["zoho-crm", "hubspot", "salesforce"]

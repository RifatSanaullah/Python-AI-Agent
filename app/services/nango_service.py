import requests
import json
import logging
from typing import Dict, Any, Optional, List
from app.config import settings

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("nango_service")

class NangoService:
    def __init__(self):
        self.base_url = settings.nango_base_url
        self.secret_key = settings.nango_secret_key
        self.headers = {
            "Authorization": f"Bearer {self.secret_key}",
            "Content-Type": "application/json"
        }
        logger.info(f"NangoService initialized with base URL: {self.base_url}")
    
    async def create_connect_session(self, end_user_id: str, allowed_integrations: List[str], 
                                     end_user_email: Optional[str] = None, 
                                     end_user_display_name: Optional[str] = None,
                                     org_id: Optional[str] = None,
                                     org_display_name: Optional[str] = None) -> Dict[str, Any]:
        """
        Create a Nango connect session to get a session token for frontend integration.
        This token allows users to connect to third-party services through Nango.
        """
        url = f"{self.base_url}/v1/connect/session"
        
        # Prepare the request payload
        payload = {
            "end_user": {
                "id": end_user_id
            },
            "allowed_integrations": allowed_integrations
        }
        
        # Add optional parameters if provided
        if end_user_email:
            payload["end_user"]["email"] = end_user_email
        if end_user_display_name:
            payload["end_user"]["display_name"] = end_user_display_name
        
        if org_id or org_display_name:
            payload["organization"] = {}
            if org_id:
                payload["organization"]["id"] = org_id
            if org_display_name:
                payload["organization"]["display_name"] = org_display_name
        
        logger.info(f"Creating Nango connect session for user {end_user_id} with integrations {allowed_integrations}")
        
        try:
            response = requests.post(url, headers=self.headers, json=payload)
            response.raise_for_status()
            result = response.json()
            logger.info(f"Successfully created Nango connect session")
            return {"sessionToken": result.get("token")}
        except requests.exceptions.RequestException as e:
            error_msg = f"Error creating Nango connect session: {str(e)}"
            if hasattr(e, 'response') and e.response is not None:
                error_msg += f" - Status code: {e.response.status_code}"
                try:
                    error_details = e.response.json()
                    error_msg += f" - Response: {error_details}"
                    logger.error(f"Nango API error details: {error_details}")
                except:
                    error_msg += f" - Response text: {e.response.text}"
                    logger.error(f"Nango API error text: {e.response.text}")
            logger.error(error_msg)
            raise Exception(error_msg)
    
    async def fetch_data(self, connection_id: str, endpoint: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        url = f"{self.base_url}/proxy/{connection_id}/{endpoint}"
        logger.info(f"Making Nango API request to: {url} with connection_id: {connection_id}")
        
        try:
            logger.info(f"Request params: {params or {}}")
            response = requests.get(url, headers=self.headers, params=params or {})
            response.raise_for_status()
            result = response.json()
            logger.info(f"Nango API request successful for endpoint: {endpoint}")
            return result
        except requests.exceptions.RequestException as e:
            error_msg = f"Error fetching data from Nango: {str(e)}"
            if hasattr(e, 'response') and e.response is not None:
                error_msg += f" - Status code: {e.response.status_code}"
                try:
                    error_details = e.response.json()
                    error_msg += f" - Response: {error_details}"
                    logger.error(f"Nango API error details: {error_details}")
                except:
                    error_msg += f" - Response text: {e.response.text}"
                    logger.error(f"Nango API error text: {e.response.text}")
            logger.error(error_msg)
            raise Exception(error_msg)
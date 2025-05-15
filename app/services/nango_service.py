import requests
import json
import logging
from typing import Dict, Any, Optional, List
from app.config import settings
import http.client

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
        # Using the correct API endpoint according to documentation
        url = f"{self.base_url.rstrip('/')}/connect/sessions"
        
        # Prepare the request payload according to documentation
        payload = {
            "end_user": {
                "id": str(end_user_id)  # Ensure ID is a string as shown in docs
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
                payload["organization"]["id"] = str(org_id)  # Ensure ID is a string
            if org_display_name:
                payload["organization"]["display_name"] = org_display_name
        
        logger.info(f"Creating Nango connect session for user {end_user_id} with integrations {allowed_integrations}")
        logger.info(f"Using endpoint: {url}")
        logger.info(f"Payload: {json.dumps(payload, indent=2)}")
        
        try:
            response = requests.post(url, headers=self.headers, json=payload)
            response.raise_for_status()
            result = response.json()
            logger.info(f"Successfully created Nango connect session", result)
            return {"sessionToken": result.get("data", {}).get("token")}
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
        
    async def delete_connect_session(self, connectionId: str) -> Dict[str, Any]:
        url = f"{self.base_url.rstrip('/')}/connection/{connectionId}"
        response = requests.request("DELETE", url)
        return response.text
    
    async def fetch_data(self, connection_id: str, endpoint: str, params: Optional[Dict[str, Any]] = None, provider = 'hubspot', sendViaBody= False) -> Dict[str, Any]:

        url = f"{self.base_url}/v1/{endpoint}"
        logger.info(f"Making Nango API request with connection_id: {connection_id}")
        
        try:
            logger.info(f"Request params: {params or {}}")
            self.headers['Connection-Id'] = connection_id
            self.headers['Provider-Config-Key'] = provider
            if sendViaBody:
                response = requests.post(url, headers=self.headers, json=params or {})
            else:
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
        
    async def post_data(self, connection_id: str, endpoint: str, payload: Optional[Dict[str, Any]] = None, provider = 'hubspot') -> Dict[str, Any]:

        url = f"{self.base_url}/v1/{endpoint}"
        logger.info(f"Making Nango API request with connection_id: {connection_id}")
        
        try:
            logger.info(f"Request payload: {payload or {}}")
            self.headers['Connection-Id'] = connection_id
            self.headers['Provider-Config-Key'] = provider
            response = requests.patch(url, headers=self.headers, json=payload)
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
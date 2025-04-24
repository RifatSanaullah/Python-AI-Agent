import requests
import json
from typing import Dict, Any, Optional, List
from app.config import settings

class NangoService:
    def __init__(self):
        self.base_url = settings.nango_base_url
        self.secret_key = settings.nango_secret_key
        self.headers = {
            "Authorization": f"Bearer {self.secret_key}",
            "Content-Type": "application/json"
        }
    
    async def fetch_data(self, connection_id: str, endpoint: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        url = f"{self.base_url}/proxy/{connection_id}/{endpoint}"
        try:
            response = requests.get(url, headers=self.headers, params=params or {})
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            error_msg = f"Error fetching data from Nango: {str(e)}"
            if hasattr(e, 'response') and e.response is not None:
                error_msg += f" - Status code: {e.response.status_code}"
                try:
                    error_msg += f" - Response: {e.response.json()}"
                except:
                    error_msg += f" - Response text: {e.response.text}"
            raise Exception(error_msg)

import httpx
from app.config import settings
from typing import Any, Dict


class BackendHandler:
    def __init__(self):
        # Define the URL of the other backend server
        self.OTHER_BACKEND_URL = settings.ai_backend_url  # Replace with your backend server URL

    async def fetch_agent(self, phoneNumber: str) -> Dict[str, Any]:

        try:
            url = f"{self.OTHER_BACKEND_URL}/agent/get-agent"
            async with httpx.AsyncClient() as client:
                response = await client.get(url, params={"phoneNumber": phoneNumber}, timeout=10.0)

            response.raise_for_status()  # Raise an exception for HTTP errors
            return response.json()

        except httpx.HTTPStatusError as e:
            raise RuntimeError(f"HTTP error while calling backend: {e.response.status_code} {e.response.text}")
        except httpx.RequestError as e:
            raise RuntimeError(f"Request error while calling backend: {str(e)}")

    async def create_call_info(self, data: Dict[str, Any]) -> Dict[str, Any]:

        try:
            url = f"{self.OTHER_BACKEND_URL}/call/create-call"
            async with httpx.AsyncClient() as client:
                response = await client.post(url, json=data, timeout=20.0)

            response.raise_for_status()  # Raise an exception for HTTP errors
            return response.json()

        except httpx.HTTPStatusError as e:
            raise RuntimeError(f"HTTP error while calling backend: {e.response.status_code} {e.response.text}")
        except httpx.RequestError as e:
            raise RuntimeError(f"Request error while calling backend: {str(e)}")


    async def update_call_info(self,data: Dict[str, Any]) -> Dict[str, Any]:

        try:
            url = f"{self.OTHER_BACKEND_URL}/call/update-call-info"
            async with httpx.AsyncClient() as client:
                response = await client.post(url, json=data, timeout=20)

            response.raise_for_status()  # Raise an exception for HTTP errors
            return response.json()

        except httpx.HTTPStatusError as e:
            raise RuntimeError(f"HTTP error while calling backend: {e.response.status_code} {e.response.text}")
        except httpx.RequestError as e:
            raise RuntimeError(f"Request error while calling backend: {str(e)}")
        
    async def update_conversation_info(self, data: Dict[str, Any]) -> Dict[str, Any]:

        try:
            url = f"{self.OTHER_BACKEND_URL}/call/update-conversation-info"
            async with httpx.AsyncClient() as client:
                response = await client.post(url, json=data, timeout=20)

            response.raise_for_status()  # Raise an exception for HTTP errors
            return response.json()

        except httpx.HTTPStatusError as e:
            raise RuntimeError(f"HTTP error while calling backend: {e.response.status_code} {e.response.text}")
        except httpx.RequestError as e:
            raise RuntimeError(f"Request error while calling backend: {str(e)}")
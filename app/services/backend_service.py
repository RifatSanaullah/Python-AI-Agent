import httpx
from app.config import settings
from typing import Any, Dict
from fastapi import FastAPI, Response

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
            print(f"HTTP error while calling backend: {e.response.status_code} {e.response.text}")
        except httpx.RequestError as e:
            print(f"Request error while calling backend: {str(e)}")

    async def connectCA(data: Dict[str, Any]) -> Dict[str, Any]:

        try:
            url = f"{settings.boom_backend_url}/call/connectCA"
            async with httpx.AsyncClient() as client:
                response = await client.post(url, json=data, timeout=20.0)

            # Return the same XML response with correct content-type
            return response.text

        except httpx.HTTPStatusError as e:
            print(f"HTTP error while calling backend: {e.response.status_code} {e.response.text}")
        except httpx.RequestError as e:
            print(f"Request error while calling backend: {str(e)}")

    async def complete_status_callback(data: Dict[str, Any]) -> Dict[str, Any]:

        try:
            url = f"{settings.boom_backend_url}/call/completeStatusCallBack"
            async with httpx.AsyncClient() as client:
                response = await client.post(url, json=data, timeout=20.0)

            response.raise_for_status()  # Raise an exception for HTTP errors
            return response.json()

        except httpx.HTTPStatusError as e:
            print(f"HTTP error while calling backend: {e.response.status_code} {e.response.text}")
        except httpx.RequestError as e:
            print(f"Request error while calling backend: {str(e)}")
            
    async def update_conversation_bh(self, data: Dict[str, Any]) -> Dict[str, Any]:

        try:
            url = f"{settings.boom_backend_url}/lead/updateConversation"
            async with httpx.AsyncClient() as client:
                response = await client.post(url, json=data, timeout=20.0)

            response.raise_for_status()  # Raise an exception for HTTP errors
            return response.json()

        except httpx.HTTPStatusError as e:
            print(f"HTTP error while calling backend: {e.response.status_code} {e.response.text}")
        except httpx.RequestError as e:
            print(f"Request error while calling backend: {str(e)}")

    async def fallback_status_callback(data: Dict[str, Any]) -> Dict[str, Any]:

        try:
            url = f"{settings.boom_backend_url}/call/callFallback"
            async with httpx.AsyncClient() as client:
                response = await client.post(url, json=data, timeout=20.0)

            response.raise_for_status()  # Raise an exception for HTTP errors
            return response.json()

        except httpx.HTTPStatusError as e:
            print(f"HTTP error while calling backend: {e.response.status_code} {e.response.text}")
        except httpx.RequestError as e:
            print(f"Request error while calling backend: {str(e)}")

    async def create_call_info(self, data: Dict[str, Any]) -> Dict[str, Any]:

        try:
            url = f"{self.OTHER_BACKEND_URL}/call/create-call"
            async with httpx.AsyncClient() as client:
                response = await client.post(url, json=data, timeout=20.0)

            response.raise_for_status()  # Raise an exception for HTTP errors
            return response.json()

        except httpx.HTTPStatusError as e:
            print(f"HTTP error while calling backend: {e.response.status_code} {e.response.text}")
        except httpx.RequestError as e:
            print(f"Request error while calling backend: {str(e)}")


    async def update_call_info(self,data: Dict[str, Any]) -> Dict[str, Any]:

        try:
            url = f"{self.OTHER_BACKEND_URL}/call/update-call-info"
            async with httpx.AsyncClient() as client:
                response = await client.post(url, json=data, timeout=20)

            response.raise_for_status()  # Raise an exception for HTTP errors
            return response.json()

        except httpx.HTTPStatusError as e:
            print(f"HTTP error while calling backend: {e.response.status_code} {e.response.text}")
        except httpx.RequestError as e:
            print(f"Request error while calling backend: {str(e)}")
        
    async def update_conversation_info(self, data: Dict[str, Any]) -> Dict[str, Any]:

        try:
            url = f"{self.OTHER_BACKEND_URL}/call/update-conversation-info"
            print(f"Updating conversation info with data: {data}")
            async with httpx.AsyncClient() as client:
                response = await client.post(url, json=data, timeout=20)

            response.raise_for_status()  # Raise an exception for HTTP errors
            result = response.json()
            print(f"Successfully updated conversation info: {result}")
            return result['data']

        except httpx.HTTPStatusError as e:
            print(f"HTTP error while updating conversation info: {e.response.status_code} {e.response.text}")
            print(f"Request data was: {data}")
            raise
        except httpx.RequestError as e:
            print(f"Request error while updating conversation info: {str(e)}")
            raise
            
    async def store_nango_connection(self, data: Dict[str, Any]) -> Dict[str, Any]:
        try:
            url = f"{self.OTHER_BACKEND_URL}/account/store-integration"
            print(f"Storing Nango connection with data: {data}")
            async with httpx.AsyncClient() as client:
                response = await client.post(url, json=data, timeout=20)
    
            response.raise_for_status()  # Raise an exception for HTTP errors
            result = response.json()
            print(f"Successfully stored Nango connection in account: {result}")
            return result
    
        except httpx.HTTPStatusError as e:
            print(f"HTTP error while storing Nango connection: {e.response.status_code} {e.response.text}")
            print(f"Request data was: {data}")
            raise
        except httpx.RequestError as e:
            print(f"Request error while storing Nango connection: {str(e)}")
            raise

    async def remove_nango_connection(self, data: Dict[str, Any]) -> Dict[str, Any]:
        try:
            url = f"{self.OTHER_BACKEND_URL}/account/remove-integration"
            print(f"Storing Nango connection with data: {data}")
            async with httpx.AsyncClient() as client:
                response = await client.post(url, json=data, timeout=20)
    
            response.raise_for_status()  # Raise an exception for HTTP errors
            result = response.json()
            print(f"Successfully stored Nango connection in account: {result}")
            return result
    
        except httpx.HTTPStatusError as e:
            print(f"HTTP error while storing Nango connection: {e.response.status_code} {e.response.text}")
            print(f"Request data was: {data}")
            raise
        except httpx.RequestError as e:
            print(f"Request error while storing Nango connection: {str(e)}")
            raise

    async def update_appointment(self, data: Dict[str, Any]) -> Dict[str, Any]:

        try:
            url = f"{self.OTHER_BACKEND_URL}/appointment/update-appointment"
            async with httpx.AsyncClient() as client:
                response = await client.post(url, json=data, timeout=20)

            response.raise_for_status()  # Raise an exception for HTTP errors
            result = response.json()
            print(f"Successfully updated conversation info: {result}")
            return result['data']

        except httpx.HTTPStatusError as e:
            print(f"HTTP error while updating conversation info: {e.response.status_code} {e.response.text}")
            print(f"Request data was: {data}")
            raise
        except httpx.RequestError as e:
            print(f"Request error while updating conversation info: {str(e)}")
            raise

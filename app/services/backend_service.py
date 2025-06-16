import httpx
from app.config import settings
from typing import Any, Dict, Optional
from fastapi import FastAPI, Response, HTTPException # Added HTTPException

class BackendHandler:
    def __init__(self):
        # Define the URL of the other backend server
        self.OTHER_BACKEND_URL = settings.ai_backend_url  # Replace with your backend server URL
        self.NODE_BACKEND_BASE_URL = settings.ai_backend_url # Assuming this is the base URL for the Node.js backend

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
            
    async def get_lead_info_boom(self, data: Dict[str, Any]) -> Dict[str, Any]:

        try:
            url = f"{settings.boom_backend_url}/lead/get-lead-by-phone"
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

    # CINC Token Management Methods
    async def store_cinc_token_in_db(self, user_id: str, token_data: Dict[str, Any]) -> None:
        """
        Calls the Node.js backend to store CINC token data.
        """
        # The Node.js backend CincTokenController.storeToken is mounted at /v1/cinc/tokens (POST)
        # The payload for that endpoint is { user_id, access_token, refresh_token, expires_in, account_id }
        # where account_id is CINC's specific account ID.
        
        # Construct the payload for the Node.js backend
        node_backend_payload = {
            "user_id": user_id, # Ensure this is a string if the backend expects it, or handle conversion
            "access_token": token_data.get("access_token"),
            "refresh_token": token_data.get("refresh_token"),
            "expires_in": token_data.get("expires_in"),
            "account_id": token_data.get("account_id") # This is CINC's specific account_id
        }

        # Validate required fields before sending
        if not all([node_backend_payload["user_id"], 
                    node_backend_payload["access_token"], 
                    node_backend_payload["refresh_token"], 
                    node_backend_payload["expires_in"]]):
            # This should ideally be caught before calling this function, but good to double check
            raise HTTPException(status_code=400, detail="Missing essential token data for Node.js backend.")

        # The URL for the Node.js backend endpoint
        # Based on AI-Agent-Backend/src/routes/v1/cincToken.ts, the route is POST /cinc/tokens (relative to /v1 base)
        url = f"{self.NODE_BACKEND_BASE_URL}/cinc/tokens"

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(url, json=node_backend_payload, timeout=10.0)
            
            response.raise_for_status() # Raise an exception for HTTP errors (4xx or 5xx)
            # If successful, the Node.js backend returns 201 with a JSON body.
            # We don't necessarily need to return its body unless specified.
            print(f"Successfully stored CINC token in Node.js backend for user {user_id}. Response: {response.json()}")

        except httpx.HTTPStatusError as e:
            # Log the error and re-raise as an HTTPException to be handled by the caller in cinc_service.py
            error_message = f"Failed to store CINC token in DB via backend: {e.response.status_code} - {e.response.text}. Payload: {node_backend_payload}"
            print(error_message)
            raise HTTPException(status_code=e.response.status_code, detail=error_message)
        except httpx.RequestError as e:
            # Network or other request-related errors
            error_message = f"Request error while calling Node.js backend to store CINC token: {str(e)}. Payload: {node_backend_payload}"
            print(error_message)
            raise HTTPException(status_code=500, detail=error_message)
        except Exception as e:
            # Catch any other unexpected errors
            error_message = f"Unexpected error storing CINC token via Node.js backend: {str(e)}. Payload: {node_backend_payload}"
            print(error_message)
            raise HTTPException(status_code=500, detail=error_message)

    async def get_cinc_token_from_db(self, user_id: str) -> Optional[Dict[str, Any]]:
        """
        Calls the Node.js backend to retrieve CINC token data.
        """
        # The Node.js backend CincTokenController.getToken is mounted at /cinc/tokens/:user_id (relative to /v1 base)
        url = f"{self.NODE_BACKEND_BASE_URL}/cinc/tokens/{user_id}"

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(url, timeout=10.0)
            
            if response.status_code == 404:
                print(f"CINC token not found in Node.js backend for user {user_id}.")
                return None # Consistent with how cinc_service.py handles not found
            
            response.raise_for_status() # Raise an exception for other HTTP errors
            token_data = response.json()
            print(f"Successfully retrieved CINC token from Node.js backend for user {user_id}.")
            return token_data

        except httpx.HTTPStatusError as e:
            error_message = f"Failed to get CINC token from DB via backend: {e.response.status_code} - {e.response.text}"
            print(error_message)
            # Propagate the status code from the backend if it's an HTTP error
            raise HTTPException(status_code=e.response.status_code, detail=error_message)
        except httpx.RequestError as e:
            error_message = f"Request error while calling Node.js backend to get CINC token: {str(e)}"
            print(error_message)
            raise HTTPException(status_code=500, detail=error_message)
        except Exception as e:
            error_message = f"Unexpected error retrieving CINC token via Node.js backend: {str(e)}"
            print(error_message)
            raise HTTPException(status_code=500, detail=error_message)

    async def delete_cinc_token_from_db(self, user_id: str) -> None:
        """
        Calls the Node.js backend to delete/invalidate CINC token data.
        """
        # The Node.js backend CincTokenController.deleteToken is mounted at /cinc/tokens/:user_id (relative to /v1 base)
        url = f"{self.NODE_BACKEND_BASE_URL}/cinc/tokens/{user_id}"

        try:
            async with httpx.AsyncClient() as client:
                response = await client.delete(url, timeout=10.0)
            
            response.raise_for_status() # Raise an exception for HTTP errors
            print(f"Successfully deleted/invalidated CINC token in Node.js backend for user {user_id}. Response: {response.json()}")

        except httpx.HTTPStatusError as e:
            error_message = f"Failed to delete CINC token from DB via backend: {e.response.status_code} - {e.response.text}"
            print(error_message)
            raise HTTPException(status_code=e.response.status_code, detail=error_message)
        except httpx.RequestError as e:
            error_message = f"Request error while calling Node.js backend to delete CINC token: {str(e)}"
            print(error_message)
            raise HTTPException(status_code=500, detail=error_message)
        except Exception as e:
            error_message = f"Unexpected error deleting CINC token via Node.js backend: {str(e)}"
            print(error_message)
            raise HTTPException(status_code=500, detail=error_message)

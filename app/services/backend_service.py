import httpx
from app.config import settings
from typing import Any, Dict, Optional
from fastapi import FastAPI, Response, HTTPException 

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
                response = await client.post(url, json=data, timeout=60)  # Increased timeout to 60 seconds

            response.raise_for_status()  # Raise an exception for HTTP errors
            result = response.json()
            print(f"Successfully updated conversation info: {result}")
            return result['data']

        except httpx.HTTPStatusError as e:
            print(f"HTTP error while updating conversation info: {e.response.status_code} {e.response.text}")
            print(f"Request data was: {data}")
            raise
        except httpx.ReadTimeout as e:
            print(f"Timeout error while updating conversation info (took longer than 60 seconds): {str(e)}")
            print(f"Request data was: {data}")
            # Return a default response instead of raising to prevent the entire call from failing
            return {"conversation": None, "summary": {}, "appointment": {"id": None}}
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
    async def store_cinc_token_in_db(self, account_id: int, token_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Calls the Node.js backend to store CINC token data.
        Returns the response data including the connection_id.
        """
        # The Node.js backend CincTokenController.storeToken is mounted at /v1/cinc/tokens (POST)
        # The payload for that endpoint is { account_id, access_token, refresh_token, expires_in, connection_id }
        # where connection_id is CINC's specific connection identifier.
        
        # Construct the payload for the Node.js backend
        node_backend_payload = {
            "account_id": account_id,
            "access_token": token_data.get("access_token"),
            "refresh_token": token_data.get("refresh_token"),
            "expires_in": token_data.get("expires_in"),
            "connection_id": token_data.get("connection_id") # This is CINC's specific connection_id
        }

        # Validate required fields before sending
        if not all([node_backend_payload["account_id"], 
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
            # Return the JSON response which includes the connection_id
            response_data = response.json()
            print(f"Successfully stored CINC token in Node.js backend for account {account_id}. Response: {response_data}")
            return response_data

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

    async def get_cinc_token_from_db(self, account_id: int, connection_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        Calls the Node.js backend to retrieve CINC token data.
        Uses account_id and optionally prioritizes connection_id from query parameters.
        """
        # The Node.js backend CincTokenController.getToken is mounted at /cinc/tokens (GET)
        # It takes account_id and optionally connection_id as query parameters.
        url = f"{self.NODE_BACKEND_BASE_URL}/cinc/tokens"
        params: Dict[str, str] = {"account_id": str(account_id)}
        if connection_id:
            params["connection_id"] = connection_id

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(url, params=params)
                response.raise_for_status()  # Raise an exception for bad status codes (4xx or 5xx)
                token_data = response.json()
                # Expected response structure from Node.js CincTokenController.getToken:
                # { access_token, refresh_token, expires_in, updated_at, account_id, connection_id }
                return token_data
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                # Consider logging: logger.info(f"No CINC token found for account_id {account_id} / connection_id {connection_id}: {e}")
                return None
            # Consider logging: logger.error(f"HTTP error fetching CINC token for account_id {account_id} / connection_id {connection_id}: {e.response.status_code} - {e.response.text}")
            raise HTTPException(status_code=e.response.status_code, detail=f"Error fetching CINC token: {e.response.text}")
        except httpx.RequestError as e:
            # Consider logging: logger.error(f"Request error fetching CINC token for account_id {account_id} / connection_id {connection_id}: {e}")
            raise HTTPException(status_code=503, detail=f"Service unavailable while fetching CINC token: {str(e)}")
        except Exception as e:
            # Consider logging: logger.error(f"Unexpected error fetching CINC token for account_id {account_id} / connection_id {connection_id}: {e}")
            raise HTTPException(status_code=500, detail=f"Unexpected error fetching CINC token: {str(e)}")

    async def delete_cinc_token_from_db(self, account_id: int, connection_id: Optional[str] = None) -> None:
        """
        Calls the Node.js backend to delete CINC token data for an account.
        Uses account_id and optionally connection_id as the primary identifiers for deletion on the backend.
        """
        # The Node.js backend CincTokenController.deleteToken is mounted at /cinc/tokens (DELETE)
        url = f"{self.NODE_BACKEND_BASE_URL}/cinc/tokens"
        params: Dict[str, str] = {"account_id": str(account_id)}
        if connection_id:
            params["connection_id"] = connection_id
            
        try:
            async with httpx.AsyncClient() as client:
                response = await client.delete(url, params=params)
                response.raise_for_status()
                # Deletion successful, no content usually returned or a success message
        except httpx.HTTPStatusError as e:
            # Consider logging: logger.error(f"HTTP error deleting CINC token for account_id {account_id} / connection_id {connection_id}: {e.response.status_code} - {e.response.text}")
            raise HTTPException(status_code=e.response.status_code, detail=f"Error deleting CINC token: {e.response.text}")
        except httpx.RequestError as e:
            # Consider logging: logger.error(f"Request error deleting CINC token for account_id {account_id} / connection_id {connection_id}: {e}")
            raise HTTPException(status_code=503, detail=f"Service unavailable while deleting CINC token: {str(e)}")
        except Exception as e:
            # Consider logging: logger.error(f"Unexpected error deleting CINC token for account_id {account_id} / connection_id {connection_id}: {e}")
            raise HTTPException(status_code=500, detail=f"Unexpected error deleting CINC token: {str(e)}")

    async def get_connection_by_id(self, connection_id: str) -> Optional[Dict[str, Any]]:
        url = f"{self.NODE_BACKEND_BASE_URL}/cinc/connection/{connection_id}"
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(url)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            print(f"HTTP error while getting connection by id: {e.response.status_code} {e.response.text}")
            raise HTTPException(status_code=e.response.status_code, detail=e.response.text)
        except httpx.RequestError as e:
            print(f"Request error while getting connection by id: {str(e)}")
            raise HTTPException(status_code=500, detail=str(e))
        except Exception as e:
            print(f"Unexpected error while getting connection by id: {str(e)}")
            raise HTTPException(status_code=500, detail=str(e))

    async def cinc_outbound_call(self, data: Dict[str, Any]) -> Dict[str, Any]:
        url = f"{self.OTHER_BACKEND_URL}/call/cinc-outbound-call"
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(url, json=data, timeout=20)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            print(f"HTTP error while calling cinc-outbound-call: {e.response.status_code} {e.response.text}")
            raise
        except httpx.RequestError as e:
            print(f"Request error while calling cinc-outbound-call: {str(e)}")
            raise

    async def get_connection_details(self, data: Dict[str, Any]) -> Dict[str, Any]:
        url = f"{self.OTHER_BACKEND_URL}/call/get-connection-details"
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(url, json=data, timeout=20)
            response.raise_for_status()
            result = response.json()
            return result['data']
        except httpx.HTTPStatusError as e:
            print(f"HTTP error while calling cinc-outbound-call: {e.response.status_code} {e.response.text}")
            raise
        except httpx.RequestError as e:
            print(f"Request error while calling cinc-outbound-call: {str(e)}")
            raise
import httpx
from app.config import settings
from typing import Any, Dict, Optional
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
    async def store_cinc_token_in_db(self, user_id: str, token_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Stores CINC token data in the database via the Express backend.
        """
        try:
            url = f"{self.OTHER_BACKEND_URL}/cinc/tokens"

            # Validate data received from CINC/token_data before constructing payload
            access_token = token_data.get("access_token")
            refresh_token = token_data.get("refresh_token")
            expires_in = token_data.get("expires_in")
            issued_at_ts = token_data.get("issued_at") # This is added by our Python's store_cinc_tokens

            if not access_token or not isinstance(access_token, str):
                raise ValueError(f"access_token from CINC is missing, empty, or not a string. Value: {access_token}")
            if not refresh_token or not isinstance(refresh_token, str):
                # Depending on OAuth flow, refresh_token might be optional on some grants, but usually not for auth code flow.
                # For CINC, it seems expected.
                raise ValueError(f"refresh_token from CINC is missing, empty, or not a string. Value: {refresh_token}")
            if expires_in is None or not isinstance(expires_in, int) or expires_in <= 0:
                # expires_in should be a positive integer (duration in seconds)
                raise ValueError(f"expires_in from CINC is missing, not a positive integer, or zero. Value: {expires_in}")
            if issued_at_ts is None or not isinstance(issued_at_ts, int):
                 raise ValueError(f"issued_at timestamp is missing or not an integer. Value: {issued_at_ts}")


            payload = {
                "user_id": user_id,
                "access_token": access_token,
                "refresh_token": refresh_token,
                "expires_in": expires_in,
                "issued_at": str(issued_at_ts), # Convert Unix timestamp to string for backend
                "scope": token_data.get("scope"),
                "token_type": token_data.get("token_type"),
                # account_id is optional in CincToken entity and controller
            }

            if not user_id or not user_id.strip():
                raise ValueError("user_id for storing token is empty or invalid.")

            print(f"Attempting to store CINC token with payload: {payload}") # Log payload

            async with httpx.AsyncClient() as client:
                response = await client.post(url, json=payload)
            
            print(f"Response from backend store token: {response.status_code} - {response.text}") # Log response
            response.raise_for_status()
            return response.json()

        except httpx.HTTPStatusError as e:
            print(f"HTTP error while storing CINC token: {e.response.status_code} {e.response.text}")
            # Consider logging e.request.content as well if debugging payload issues
            raise
        except httpx.RequestError as e:
            print(f"Request error while storing CINC token: {str(e)}")
            raise
        except ValueError as ve: # Catch our validation errors
            print(f"Validation error before storing CINC token: {ve}")
            # Re-raise as HTTPException or let it propagate if appropriate
            raise HTTPException(status_code=400, detail=str(ve))

    async def get_cinc_token_from_db(self, user_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieves CINC token data from the database via the Express backend.
        """
        try:
            url = f"{self.OTHER_BACKEND_URL}/cinc/tokens/{user_id}" # Assuming Express backend endpoint
            async with httpx.AsyncClient() as client:
                response = await client.get(url)
            if response.status_code == 404:
                return None
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            print(f"HTTP error while fetching CINC token: {e.response.status_code} {e.response.text}")
            # Potentially return None or raise a custom error
            if e.response.status_code == 404:
                return None
            raise
        except httpx.RequestError as e:
            print(f"Request error while fetching CINC token: {str(e)}")
            raise

    async def delete_cinc_token_from_db(self, user_id: str) -> Dict[str, Any]:
        """
        Deletes CINC token data from the database via the Express backend.
        """
        try:
            url = f"{self.OTHER_BACKEND_URL}/cinc/tokens/{user_id}" # Assuming Express backend endpoint
            async with httpx.AsyncClient() as client:
                response = await client.delete(url)
            response.raise_for_status()
            return response.json() # Or simply return a success status/message
        except httpx.HTTPStatusError as e:
            print(f"HTTP error while deleting CINC token: {e.response.status_code} {e.response.text}")
            raise
        except httpx.RequestError as e:
            print(f"Request error while deleting CINC token: {str(e)}")
            raise

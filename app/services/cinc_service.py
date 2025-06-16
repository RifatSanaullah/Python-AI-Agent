import logging
import requests
import httpx
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any, List

from fastapi import HTTPException, status
from app.config import settings
from app.services.backend_service import BackendHandler

CINC_AUTH_BASE_URL = "https://authv2.cincapi.com/integrator"
CINC_API_BASE_URL = "https://public.cincapi.com/v2"

_backend_handler = BackendHandler()

async def store_cinc_tokens(account_id: int, token_data: Dict[str, Any]):
    payload = {
        "account_id": account_id,
        "access_token": token_data.get("access_token"),
        "refresh_token": token_data.get("refresh_token"),
        "expires_in": token_data.get("expires_in"),
        "connection_id": token_data.get("connection_id"), # CINC's specific connection_id
    }
    if not all([payload["account_id"], payload["access_token"], payload["refresh_token"], payload["expires_in"]]):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing essential token data for storage.")

    try:
        await _backend_handler.store_cinc_token_in_db(account_id=account_id, token_data=payload)
    except HTTPException as e:
        raise e
    except Exception as e:
        print(f"Error calling backend to store CINC token for account {account_id}: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to store CINC token via backend: {str(e)}")

async def get_cinc_tokens(account_id: int, connection_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
    try:
        # Use connection_id if provided, otherwise fall back to account_id for lookup
        token_data = await _backend_handler.get_cinc_token_from_db(account_id, connection_id=connection_id)
        return token_data
    except HTTPException as e:
        # Log or handle the exception from the backend service call
        # For example, if a 404 is raised, it means token not found, which is a valid case for returning None
        if e.status_code == 404:
            return None
        # Re-raise other HTTPExceptions or handle them as needed
        raise
    except Exception as e:
        # Log or handle other unexpected errors
        # print(f"Unexpected error in get_cinc_tokens: {e}") # Replace with proper logging
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error retrieving CINC tokens")

async def delete_cinc_tokens(account_id: int, connection_id: Optional[str] = None):
    try:
        await _backend_handler.delete_cinc_token_from_db(account_id, connection_id=connection_id)
    except HTTPException as e:
        raise e
    except Exception as e:
        print(f"Error calling backend to delete CINC token for account {account_id}: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to delete CINC token via backend: {str(e)}")

async def get_cinc_access_token(account_id: int, connection_id: Optional[str] = None) -> str:
    tokens = await get_cinc_tokens(account_id, connection_id=connection_id)
    if not tokens or not tokens.get("access_token"):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="CINC access token not found for account.")
    token_updated_at_str = tokens.get("updated_at")
    expires_in_seconds = tokens.get("expires_in")

    if not token_updated_at_str or expires_in_seconds is None:
        print(f"Warning: Missing updated_at or expires_in for CINC token account {account_id}. Proceeding with current token.")
        return tokens["access_token"]

    try:
        # Parse the timestamp string (assuming ISO 8601 format from backend)
        # Example: "2024-06-15T12:00:00.000Z"
        # Ensure the timestamp is timezone-aware (UTC)
        if token_updated_at_str.endswith('Z'):
            updated_at = datetime.fromisoformat(token_updated_at_str[:-1] + '+00:00')
        else:
            updated_at = datetime.fromisoformat(token_updated_at_str) # Or parse according to actual format
            if updated_at.tzinfo is None:
                updated_at = updated_at.replace(tzinfo=timezone.utc) # Assume UTC if no tzinfo

        expiration_time = updated_at + timedelta(seconds=int(expires_in_seconds))

        if datetime.now(timezone.utc) >= expiration_time:
            refreshed_tokens = await refresh_access_token(account_id, connection_id=connection_id) # Pass connection_id
            return refreshed_tokens["access_token"]

    except ValueError as ve:
        refreshed_tokens = await refresh_access_token(account_id, connection_id=connection_id) # Pass connection_id
        return refreshed_tokens["access_token"]
    except Exception as e:
        refreshed_tokens = await refresh_access_token(account_id, connection_id=connection_id) # Pass connection_id
        return refreshed_tokens["access_token"]

    return tokens["access_token"]

def get_authorization_url(state: Optional[str] = None, user_id: Optional[str] = None) -> str:
    auth_url = f"{CINC_AUTH_BASE_URL}/authorize" 
    composite_state_parts = []
    if state:
        composite_state_parts.append(state)
    if user_id:
        composite_state_parts.append(user_id)
    
    final_composite_state = "__".join(composite_state_parts) if composite_state_parts else "default_state"

    params: Dict[str, Any] = {
        'client_id': settings.cinc_client_id,
        'response_type': 'code',
        'redirect_uri': settings.cinc_redirect_uri,
        'scope': 'api:read api:create api:update api:event',
        'state': final_composite_state
    }
    
    import requests 
    prepared_request = requests.Request('GET', auth_url, params=params).prepare()
    if prepared_request.url is None:
        raise HTTPException(status_code=500, detail="Failed to prepare CINC authorization URL")
    return prepared_request.url

async def exchange_code_for_token(auth_code: str, composite_state: Optional[str]) -> Dict[str, Any]: 
    token_url = f"{CINC_AUTH_BASE_URL}/token"
    user_id_for_storage = None
    original_csrf_state = None 

    if composite_state:
        state_parts = composite_state.split("__")
        if len(state_parts) == 2:
            original_csrf_state = state_parts[0]
            user_id_for_storage = state_parts[1]
        elif len(state_parts) == 1:
            user_id_for_storage = state_parts[-1]

    if not user_id_for_storage:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="User ID could not be determined from state. Cannot store token.")

    payload = {
        'grant_type': 'authorization_code',
        'code': auth_code,
        'redirect_uri': settings.cinc_redirect_uri,
        'client_id': settings.cinc_client_id,
        'client_secret': settings.cinc_client_secret
    }

    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(token_url, data=payload)
            response.raise_for_status()
            token_data = response.json()
            storage_payload = {
                "access_token": token_data.get("access_token"),
                "refresh_token": token_data.get("refresh_token"),
                "expires_in": token_data.get("expires_in"),
                "connection_id": token_data.get("connection_id"), # CINC's specific connection_id
                "account_id": token_data.get("account_id") # CINC's account_id should come from token response
            }

            # For OAuth flow, we need to convert user_id to account_id
            # In a real system, you'd look up the account_id from user_id
            # For now, assuming user_id_for_storage can be used as account_id or convert it
            try:
                account_id_for_storage = int(user_id_for_storage)  # Assuming user_id can be converted to account_id
            except ValueError:
                # If user_id is not a number, we might need to look it up from the backend
                # For now, raise an error - this should be handled properly in production
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot determine account_id for token storage")

            await store_cinc_tokens(account_id=account_id_for_storage, token_data=storage_payload)
            
            return {**token_data, "user_id_for_storage": user_id_for_storage, "original_csrf_state": original_csrf_state}
        except httpx.HTTPStatusError as e:
            error_detail = f"CINC token exchange failed: {e.response.status_code} - {e.response.text}"
            print(error_detail)
            raise HTTPException(status_code=e.response.status_code, detail=error_detail)
        except httpx.RequestError as e:
            error_detail = f"Request to CINC token endpoint failed: {str(e)}"
            print(error_detail)
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=error_detail)
        except Exception as e:
            error_detail = f"An unexpected error occurred during token exchange: {str(e)}"
            print(error_detail)
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=error_detail)

async def refresh_access_token(account_id: int, connection_id: Optional[str] = None) -> Dict[str, Any]:
    token_url = f"{CINC_AUTH_BASE_URL}/token"
    
    # Fetch current tokens using account_id and potentially connection_id
    current_tokens = await get_cinc_tokens(account_id, connection_id=connection_id)
    if not current_tokens or not current_tokens.get("refresh_token"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No refresh token available to refresh CINC access token.")

    payload = {
        'grant_type': 'refresh_token',
        'refresh_token': current_tokens["refresh_token"],
        'client_id': settings.cinc_client_id,
        'client_secret': settings.cinc_client_secret
    }
    import httpx # Ensure httpx is imported
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(token_url, data=payload)
            response.raise_for_status()
            new_token_data = response.json()

            # Prepare payload for storage, similar to exchange_code_for_token
            storage_payload = {
                "access_token": new_token_data.get("access_token"),
                "refresh_token": new_token_data.get("refresh_token"), # CINC may or may not return a new refresh token
                "expires_in": new_token_data.get("expires_in"),
                "account_id": current_tokens.get("account_id"), # Preserve original CINC account_id
            }
            # If CINC returns a new refresh token, use it. Otherwise, the old one might still be valid or needs to be preserved.
            if not storage_payload["refresh_token"]:
                 storage_payload["refresh_token"] = current_tokens["refresh_token"] # Keep old if not in new response

            await store_cinc_tokens(account_id, storage_payload) # account_id is the key for storing
            return storage_payload  # Return the storage_payload which has all required fields
        except httpx.HTTPStatusError as e:
            error_detail = f"CINC token refresh failed: {e.response.status_code} - {e.response.text}"
            print(error_detail)
            # If refresh fails (e.g. 400, 401), it might mean the refresh token is also invalid.
            # The user might need to re-authenticate.
            # Consider deleting the stored tokens or marking them as invalid.
            if e.response.status_code in [400, 401]:
                try:
                    await delete_cinc_tokens(account_id, connection_id=connection_id) 
                except Exception as del_e:
                    print(f"Failed to delete tokens for account {account_id} after refresh failure: {del_e}")
            raise HTTPException(status_code=e.response.status_code, detail=error_detail)
        except Exception as e:
            error_detail = f"Error during CINC token refresh: {str(e)}"
            print(error_detail)
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=error_detail)

async def _make_cinc_request(method: str, endpoint: str, account_id: int, connection_id: Optional[str] = None, params: Optional[Dict[str, Any]] = None, json_data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    access_token = await get_cinc_access_token(account_id, connection_id=connection_id)
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
        "Accept": "application/json"
    }
    url = f"{CINC_API_BASE_URL}{endpoint}"

    # Debug logging
    print(f"DEBUG - CINC API Request:")
    print(f"  Method: {method}")
    print(f"  URL: {url}")
    print(f"  Headers: {headers}")
    if json_data:
        print(f"  JSON Data: {json_data}")
    if params:
        print(f"  Params: {params}")

    async with httpx.AsyncClient() as client:
        try:
            if method.upper() == 'GET':
                response = await client.get(url, headers=headers, params=params)
            elif method.upper() == 'POST':
                response = await client.post(url, headers=headers, json=json_data, params=params)
            elif method.upper() == 'PUT':
                response = await client.put(url, headers=headers, json=json_data, params=params)
            elif method.upper() == 'PATCH':
                response = await client.patch(url, headers=headers, json=json_data, params=params)
            # Add other methods like DELETE if needed
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")

            print(f"DEBUG - CINC API Response: {response.status_code}")
            response.raise_for_status()
            response_data = response.json()
            print(f"DEBUG - CINC API Response Data: {response_data}")
            return response_data
        except httpx.HTTPStatusError as e:
            error_text = e.response.text
            print(f"CINC API request failed: {e.response.status_code} - {error_text} for URL: {url}")
            print(f"DEBUG - Full error response headers: {e.response.headers}")
            
            # Try to parse error details if it's JSON
            try:
                error_json = e.response.json()
                print(f"DEBUG - Error JSON details: {error_json}")
            except:
                print(f"DEBUG - Error response is not JSON: {error_text}")
                
            raise HTTPException(status_code=e.response.status_code, detail=f"CINC API request error: {error_text}")
        except Exception as e:
            print(f"Error making CINC API request: {e} for URL: {url}")
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to make CINC API request.")

async def get_leads(account_id: int, connection_id: Optional[str] = None, offset: int = 0, limit: int = 10, next_page: Optional[str] = None, from_lead_id: Optional[str] = None) -> Dict[str, Any]:
    endpoint = "/site/leads"
    params = {
        "offset": offset,
        "limit": limit
    }
    if next_page:
        params["next"] = next_page
    if from_lead_id:
        params["from"] = f"id:{from_lead_id}"
    return await _make_cinc_request("GET", endpoint, account_id, connection_id=connection_id, params=params)

async def get_lead_details(account_id: int, lead_id: str, connection_id: Optional[str] = None, fields: Optional[List[str]] = None) -> Dict[str, Any]:    
    endpoint = f"/site/leads/{lead_id}"
    params = {}
    if fields:
        params["fields"] = ",".join(fields)
    return await _make_cinc_request("GET", endpoint, account_id, connection_id=connection_id, params=params)

async def create_lead(account_id: int, lead_data: Dict[str, Any], connection_id: Optional[str] = None) -> Dict[str, Any]:    
    endpoint = "/site/leads"
    return await _make_cinc_request("POST", endpoint, account_id, connection_id=connection_id, json_data=lead_data)

async def update_lead(account_id: int, lead_id: str, lead_data: Dict[str, Any], connection_id: Optional[str] = None) -> Dict[str, Any]:    
    endpoint = f"/site/leads/{lead_id}"
    return await _make_cinc_request("PATCH", endpoint, account_id, connection_id=connection_id, json_data=lead_data)




# OAuth Flow Notes:
# 1. Your FastAPI app needs an endpoint that calls `get_authorization_url()` and redirects the user.
# 2. User authorizes your app on CINC.
# 3. CINC redirects to your `redirect_uri` with `code` and `state`.
# 4. Your callback endpoint calls `exchange_code_for_token(code)`.
# 5. Securely store `access_token` and `refresh_token` (e.g., in DB, associated with user/integration ID).
#    The `store_cinc_tokens` placeholder function is called by `exchange_code_for_token` and `refresh_access_token`.
# 6. Use `user_id` with API call functions (e.g., `get_leads(user_id)`).
#    The `_make_cinc_request` helper now uses `get_cinc_access_token(user_id)` which includes refresh logic.
# 7. If refresh fails (e.g., refresh token also invalid), the user must re-authenticate (go to step 1).

import httpx # Ensure httpx is imported
import time
from fastapi import HTTPException, status
from app.config import settings
from typing import Optional, Dict, Any, List
from app.services.backend_service import BackendHandler
import requests # Added for requests.Request

CINC_AUTH_BASE_URL = "https://authv2.cincapi.com/integrator"
CINC_API_BASE_URL = "https://public.cincapi.com/v2"

# Initialize BackendHandler instance to be used by CINC service
# This assumes BackendHandler doesn't require async context for initialization
# If it does, this needs to be handled differently (e.g., dependency injection in FastAPI routes)
_backend_handler = BackendHandler()

async def store_cinc_tokens(user_id: str, token_data: Dict[str, Any]):
    """
    Stores CINC tokens for a user via BackendHandler.
    Adds 'issued_at' timestamp to token_data before storing.
    """
    try:
        # Add 'issued_at' timestamp before storing, CINC provides 'expires_in'
        token_data['issued_at'] = int(time.time()) # Current time as Unix timestamp
        await _backend_handler.store_cinc_token_in_db(user_id, token_data)
    except HTTPException as e: # Catch HTTPException specifically if backend_handler raises it
        print(f"HTTPException during token storage process for user {user_id}: {e.detail}")
        raise e # Re-raise it, it's already an HTTPException
    except Exception as e:
        print(f"Unexpected error in store_cinc_tokens for user {user_id}: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Unexpected error storing CINC tokens: {str(e)}")

async def get_cinc_tokens(user_id: str) -> Optional[Dict[str, Any]]:
    """
    Retrieves CINC tokens for a user via BackendHandler.
    """
    try:
        return await _backend_handler.get_cinc_token_from_db(user_id)
    except Exception as e:
        print(f"Error in get_cinc_tokens: {e}")
        # Optionally, re-raise or handle as appropriate
        return None

async def delete_cinc_tokens(user_id: str):
    """
    Deletes CINC tokens for a user via BackendHandler.
    """
    try:
        await _backend_handler.delete_cinc_token_from_db(user_id)
    except Exception as e:
        print(f"Error in delete_cinc_tokens: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to delete CINC tokens")

async def get_cinc_access_token(user_id: str) -> str:
    """
    Retrieves a valid CINC access token for the user.
    Handles token refresh if necessary.
    """
    tokens = await get_cinc_tokens(user_id)
    if not tokens or not tokens.get("access_token"):
        print(f"No CINC tokens found for user_id: {user_id}")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="CINC integration not found or token missing. Please re-authenticate.")

    # Check if the access token is expired
    issued_at = tokens.get("issued_at")
    expires_in = tokens.get("expires_in")

    # Ensure issued_at and expires_in are numbers for comparison
    try:
        # The stored issued_at is already a timestamp (number). expires_in is also a number.
        # If they are stored as strings in the DB, they need conversion here.
        # Assuming they are retrieved as numbers from backend_service/DB
        current_time = int(time.time())
        if isinstance(issued_at, (str, bytes)):
            issued_at = int(issued_at)
        if isinstance(expires_in, (str, bytes)):
            expires_in = int(expires_in)

        if not isinstance(issued_at, (int, float)) or not isinstance(expires_in, (int, float)):
            print(f"Invalid token timing information for user {user_id}. issued_at: {issued_at}, expires_in: {expires_in}")
            # Fallback to trying to refresh or re-authenticate
            refreshed_tokens = await refresh_access_token(user_id)
            return refreshed_tokens["access_token"]

        # Add a small buffer (e.g., 60 seconds) to refresh before actual expiry
        if current_time >= issued_at + expires_in - 60:
            print(f"CINC access token expired for user {user_id}. Refreshing...")
            refreshed_tokens = await refresh_access_token(user_id)
            return refreshed_tokens["access_token"]
    except ValueError as ve:
        print(f"ValueError during token expiry check for user {user_id}: {ve}. Attempting refresh.")
        refreshed_tokens = await refresh_access_token(user_id)
        return refreshed_tokens["access_token"]
    except Exception as e:
        print(f"Unexpected error during token expiry check for user {user_id}: {e}. Attempting refresh.")
        # Fallback or re-raise depending on desired behavior
        refreshed_tokens = await refresh_access_token(user_id)
        return refreshed_tokens["access_token"]

    return tokens["access_token"]

def get_authorization_url(state: Optional[str] = None, user_id: Optional[str] = None) -> str:
    """
    Generates the CINC authorization URL to redirect the user to.
    Includes user_id in the state if provided.
    """
    auth_url = f"{CINC_AUTH_BASE_URL}/authorize"

    # Combine state (CSRF token from frontend) and user_id
    final_composite_state = state if state else "default_csrf_state" # Base CSRF state
    if user_id:
        final_composite_state = f"{final_composite_state}:UID:{user_id}"

    params: Dict[str, Any] = {
        'client_id': settings.cinc_client_id,
        'response_type': 'code',
        'redirect_uri': settings.cinc_redirect_uri,
        'scope': 'api:read api:create api:update api:event', # Ensure all needed scopes
    }
    if final_composite_state:
        params['state'] = final_composite_state
    
    # Using requests.Request to prepare the URL, as was in the original summarized code
    # This is fine for URL construction.
    prepared_request = requests.Request('GET', auth_url, params=params).prepare()
    if prepared_request.url is None:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Could not prepare CINC authorization URL")
    return prepared_request.url

async def exchange_code_for_token(auth_code: str, user_id_for_storage: str) -> Dict[str, Any]: # Added user_id_for_storage
    """
    Exchanges an authorization code for an access token and stores it via BackendHandler.
    """
    token_url = f"{CINC_AUTH_BASE_URL}/token"
    payload = {
        'grant_type': 'authorization_code',
        'code': auth_code,
        'client_id': settings.cinc_client_id,
        'client_secret': settings.cinc_client_secret,
        'redirect_uri': settings.cinc_redirect_uri # This must match the URI used in the auth request
    }
    headers = {
        'Content-Type': 'application/x-www-form-urlencoded'
    }
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(token_url, data=payload, headers=headers)
            response.raise_for_status() # Raise an exception for HTTP errors (4xx or 5xx)
            token_data = response.json()
            # Store the tokens using the provided user_id_for_storage
            await store_cinc_tokens(user_id_for_storage, token_data)
            return token_data
        except httpx.HTTPStatusError as e:
            print(f"HTTP error exchanging CINC code for token: {e.response.status_code} - {e.response.text}")
            raise HTTPException(status_code=e.response.status_code, detail=f"CINC token exchange failed: {e.response.text}")
        except Exception as e:
            print(f"Error exchanging CINC code for token: {e}")
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to exchange CINC authorization code for token.")

async def refresh_access_token(user_id_for_storage: str) -> Dict[str, Any]:
    """
    Refreshes the CINC access token using the stored refresh token.
    Updates the stored tokens with the new ones. If CINC doesn't return a new
    refresh_token, the existing one is preserved.
    """
    tokens = await get_cinc_tokens(user_id_for_storage)
    if not tokens or not tokens.get('refresh_token'):
        print(f"No CINC refresh token found for user_id: {user_id_for_storage} to refresh.")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="CINC refresh token not found. Please re-authenticate.")

    token_url = f"{CINC_AUTH_BASE_URL}/token"
    payload = {
        'grant_type': 'refresh_token',
        'refresh_token': tokens['refresh_token'],
        'client_id': settings.cinc_client_id,
        'client_secret': settings.cinc_client_secret,
        'redirect_uri': settings.cinc_redirect_uri,
        'scope': tokens.get('scope', 'api:read api:create api:update api:event')
    }
    headers = {
        'Content-Type': 'application/x-www-form-urlencoded'
    }

    async with httpx.AsyncClient() as client:
        try:
            print(f"Refreshing CINC token for user {user_id_for_storage} with payload: {payload}")
            response = await client.post(token_url, data=payload, headers=headers)
            response.raise_for_status()
            new_token_data_from_cinc = response.json()

            # Prepare the data to be stored. Start with new data from CINC.
            data_to_store = new_token_data_from_cinc.copy()

            # If CINC did not return a new refresh_token, use the old (existing) one.
            if 'refresh_token' not in data_to_store or data_to_store['refresh_token'] is None:
                if tokens.get('refresh_token'): # Ensure the old token had one
                    print(f"CINC refresh response for user {user_id_for_storage} did not include a new refresh_token. Using the existing one.")
                    data_to_store['refresh_token'] = tokens['refresh_token']
                else:
                    # This case implies the original tokens['refresh_token'] was also None or missing,
                    # which should have been caught earlier. If not, validation in store_cinc_token_in_db will fail.
                    print(f"Warning: CINC refresh response for user {user_id_for_storage} missing refresh_token, and no old one available/valid in current context.")

            # The store_cinc_tokens function will add/update 'issued_at'.
            await store_cinc_tokens(user_id_for_storage, data_to_store)
            print(f"CINC token refreshed and stored for user {user_id_for_storage}")
            return data_to_store # Return the data that was processed for storage
        except httpx.HTTPStatusError as e:
            print(f"HTTP error refreshing CINC token for user {user_id_for_storage}: {e.response.status_code} - {e.response.text}")
            if e.response.status_code == 400 or e.response.status_code == 401: # Bad request or Unauthorized (e.g. invalid refresh token)
                print(f"CINC refresh token likely invalid for user {user_id_for_storage}. Deleting stored tokens.")
                await delete_cinc_tokens(user_id_for_storage) # Delete tokens to force re-auth
                raise HTTPException(status_code=e.response.status_code, detail=f"CINC token refresh failed: {e.response.text}. Please re-authenticate.")
            raise HTTPException(status_code=e.response.status_code, detail=f"CINC token refresh failed: {e.response.text}")
        except Exception as e:
            print(f"Error refreshing CINC token for user {user_id_for_storage}: {e}")
            # Consider if deleting tokens is appropriate here too, or if it's a transient network issue.
            # For now, raising a generic 500.
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to refresh CINC access token: {str(e)}")

async def _make_cinc_request(method: str, endpoint: str, user_id: str, params: Optional[Dict[str, Any]] = None, json_data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    access_token = await get_cinc_access_token(user_id)
    headers = {
        'Authorization': f'Bearer {access_token}',
        'Content-Type': 'application/json'
    }
    url = f"{CINC_API_BASE_URL}{endpoint}"

    async with httpx.AsyncClient() as client:
        try:
            if method.upper() == 'GET':
                response = await client.get(url, headers=headers, params=params)
            elif method.upper() == 'POST':
                response = await client.post(url, headers=headers, json=json_data, params=params)
            elif method.upper() == 'PUT':
                response = await client.put(url, headers=headers, json=json_data, params=params)
            # Add other methods like DELETE if needed
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")

            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            print(f"CINC API request failed: {e.response.status_code} - {e.response.text} for URL: {url}")
            # Removed token deletion on 401 to avoid forcing re-authentication on transient errors.
            # if e.response.status_code == 401: 
            #     await delete_cinc_tokens(user_id) # Clean up potentially invalid tokens
            #     raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="CINC API request unauthorized. Token may be invalid. Please re-authenticate.")
            raise HTTPException(status_code=e.response.status_code, detail=f"CINC API request error: {e.response.text}")
        except Exception as e:
            print(f"Error making CINC API request: {e} for URL: {url}")
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to make CINC API request.")

async def get_leads(user_id: str, offset: int = 0, limit: int = 10, next_page: Optional[str] = None, from_lead_id: Optional[str] = None) -> Dict[str, Any]: # Changed access_token to user_id
    endpoint = "/site/leads"
    params: Dict[str, Any] = {"offset": offset, "limit": limit} # Explicitly type params
    if next_page:
        params["next"] = next_page
    if from_lead_id:
        params["from"] = f"id:{from_lead_id}"
    return await _make_cinc_request("GET", endpoint, user_id, params=params)

async def get_lead_details(user_id: str, lead_id: str, fields: Optional[List[str]] = None) -> Dict[str, Any]:    
    endpoint = f"/site/leads/{lead_id}"
    params: Dict[str, Any] = {} # Explicitly type params
    if fields:
        params["fields"] = ",".join(fields)
    return await _make_cinc_request("GET", endpoint, user_id, params=params)

async def create_lead(user_id: str, lead_data: Dict[str, Any]) -> Dict[str, Any]:    
    endpoint = "/site/leads"
    # Ensure email is present as per CINC docs for creation
    if not lead_data.get("info", {}).get("contact", {}).get("email"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email is required to create a CINC lead.")
    return await _make_cinc_request("POST", endpoint, user_id, json_data=lead_data)

async def update_lead(user_id: str, lead_id: str, lead_data: Dict[str, Any]) -> Dict[str, Any]:    
    endpoint = f"/site/leads/{lead_id}"
    # CINC docs state: "The field email is required to uniquely identify the lead on that site and cannot be changed."
    # However, the POST /site/leads (upsert) mentions username can be used for email change.
    # For POST /site/leads/{lead_id}, it's safer to assume email in payload is for identification if not changing, or not include if not changing.
    # The example for POST /site/leads/{lead_id} includes email in the payload.
    return await _make_cinc_request("POST", endpoint, user_id, json_data=lead_data) # CINC uses POST for updates to specific lead ID

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

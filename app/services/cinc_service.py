import httpx 
import time
from fastapi import HTTPException, status
from app.config import settings
from typing import Optional, Dict, Any, List
from app.services.backend_service import BackendHandler
import requests 

CINC_AUTH_BASE_URL = "https://authv2.cincapi.com/integrator"
CINC_API_BASE_URL = "https://public.cincapi.com/v2"

_backend_handler = BackendHandler() # Keep this instance for other backend calls

async def store_cinc_tokens(user_id: str, token_data: Dict[str, Any]):
    """
    Stores CINC token data by calling the backend service, which now saves to the Connection table.
    The backend service expects: user_id, access_token, refresh_token, expires_in, and optionally cinc_account_id.
    """
    payload = {
        "user_id": user_id,
        "access_token": token_data.get("access_token"),
        "refresh_token": token_data.get("refresh_token"),
        "expires_in": token_data.get("expires_in"),
        "account_id": token_data.get("account_id"), # This is CINC's specific account ID
        # issued_at is not stored in Connection table directly, created_at/updated_at are used by DB
    }
    # Validate required fields before sending to backend
    if not all([payload["user_id"], payload["access_token"], payload["refresh_token"], payload["expires_in"]]):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing essential token data for storage.")

    try:
        # Assuming the backend handler's store_cinc_token_in_db method is updated
        # to match the CincTokenController's new logic (i.e., saves to 'connections' table).
        await _backend_handler.store_cinc_token_in_db(user_id=user_id, token_data=payload)
        # No specific return needed if backend handles confirmation, or adjust as per backend response
    except HTTPException as e:
        # Re-raise HTTPException from backend_handler to propagate specific errors
        raise e
    except Exception as e:
        # Log the full error for debugging
        print(f"Error calling backend to store CINC token for user {user_id}: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to store CINC token via backend: {str(e)}")

async def get_cinc_tokens(user_id: str) -> Optional[Dict[str, Any]]:
    """
    Retrieves CINC token data (access_token, refresh_token, expires_in) from the backend service.
    The backend service now fetches from the Connection table.
    """
    try:
        # This backend method should now fetch from the Connection table via CincTokenController.getToken
        token_data = await _backend_handler.get_cinc_token_from_db(user_id)
        if not token_data or not token_data.get("access_token"):
            return None # Or raise HTTPException(status_code=404, detail="Token not found")
        
        # The backend should return access_token, refresh_token, expires_in.
        # It might also return created_at/updated_at from the Connection table if needed for expiry calc here.
        # For simplicity, assume backend returns what's needed, including a way to check expiry if not raw expires_in.
        return token_data
    except HTTPException as e:
        if e.status_code == 404:
            return None # Consistent with original behavior for not found
        raise e # Re-raise other HTTPExceptions
    except Exception as e:
        print(f"Error calling backend to get CINC token for user {user_id}: {e}")
        # Consider if this should be a 404 or 500 depending on expected backend behavior
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to retrieve CINC token via backend: {str(e)}")

async def delete_cinc_tokens(user_id: str):
    """
    Requests deletion/invalidation of CINC token data via the backend service.
    The backend service now updates the Connection table (e.g., nullifies tokens, sets status to inactive).
    """
    try:
        # This backend method should now trigger CincTokenController.deleteToken
        await _backend_handler.delete_cinc_token_from_db(user_id)
        # No specific return needed if backend handles confirmation
    except HTTPException as e:
        raise e
    except Exception as e:
        print(f"Error calling backend to delete CINC token for user {user_id}: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to delete CINC token via backend: {str(e)}")

async def get_cinc_access_token(user_id: str) -> str:
    tokens = await get_cinc_tokens(user_id)
    if not tokens or not tokens.get("access_token"):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="CINC access token not found for user.")

    # Check if the access token is expired
    # The `expires_in` is a duration. The `issued_at` (or `updated_at` from Connection table)
    # is needed to determine if `access_token` is stale.
    # The `get_cinc_tokens` should ideally return `updated_at` (when token was last stored/refreshed)
    # or the backend should handle refresh transparently if it can.

    # Assuming `get_cinc_tokens` returns `expires_in` and `updated_at` (as `token_updated_at` for clarity)
    token_updated_at_str = tokens.get("updated_at") # This would come from Connection.updated_at
    expires_in_seconds = tokens.get("expires_in")

    if not token_updated_at_str or expires_in_seconds is None:
        # Not enough info to check expiry, assume valid or try refresh if refresh token exists
        # For robust solution, this path should be an error or trigger refresh
        print(f"Warning: Missing updated_at or expires_in for CINC token user {user_id}. Proceeding with current token.")
        return tokens["access_token"]

    try:
        # Parse updated_at string (assuming ISO format from backend) to datetime object
        # Make sure the string format matches what the backend sends.
        # Python's datetime.fromisoformat expects a specific format.
        # If it's a Unix timestamp string, convert appropriately.
        # For this example, assuming it's a string that needs parsing.
        # If it's already a datetime object from backend (unlikely over HTTP), adjust.
        # Let's assume backend sends it in a way that can be parsed or is a timestamp.
        # OR, if the backend CincTokenController.getToken returns `expires_in` and we rely on `updated_at`
        # from the Connection table, then the Python backend service needs to fetch that `updated_at`.

        # Simplified logic: If a refresh is needed, the API call will fail, then refresh will be attempted.
        # This is less proactive than checking expiry here.
        # A more robust check:
        # from datetime import datetime, timedelta, timezone
        # updated_at_dt = datetime.fromisoformat(token_updated_at_str.replace('Z', '+00:00')) # Example for ISO string
        # if datetime.now(timezone.utc) > (updated_at_dt + timedelta(seconds=expires_in_seconds)):
        # print(f"CINC token for user {user_id} expired. Attempting refresh.")
        # refreshed_tokens = await refresh_access_token(user_id)
        # return refreshed_tokens["access_token"]
        pass # Placeholder for more robust expiry check

    except ValueError as ve:
        print(f"Error parsing date for CINC token expiry check (user {user_id}): {ve}. Using current token.")
    except Exception as e:
        print(f"Error during CINC token expiry check (user {user_id}): {e}. Using current token.")
        # Potentially log this error more formally

    return tokens["access_token"]

def get_authorization_url(state: Optional[str] = None, user_id: Optional[str] = None) -> str:
    auth_url = f"{CINC_AUTH_BASE_URL}/authorize" # Corrected base URL part

    # Combine CSRF state (from frontend) and user_id into a single state parameter for CINC
    # This composite state will be returned by CINC and can be parsed in the callback.
    # Example: "csrfToken_userId"
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
        'scope': 'api:read api:create api:update api:event', # Standard CINC scopes
        'state': final_composite_state
    }
    
    # Use requests to build the URL correctly with parameters
    # This import should be at the top of the file
    import requests 
    prepared_request = requests.Request('GET', auth_url, params=params).prepare()
    if prepared_request.url is None:
        raise HTTPException(status_code=500, detail="Failed to prepare CINC authorization URL")
    return prepared_request.url

async def exchange_code_for_token(auth_code: str, composite_state: Optional[str]) -> Dict[str, Any]: 
    """
    Exchanges an authorization code for an access token and stores it via BackendHandler.
    Extracts user_id from the composite_state to associate the token correctly.
    Returns a dictionary containing the token data and the user_id that was used for storage.
    """
    token_url = f"{CINC_AUTH_BASE_URL}/token" # Corrected base URL part

    user_id_for_storage = None
    original_csrf_state = None 

    if composite_state:
        state_parts = composite_state.split("__")
        if len(state_parts) == 2:
            original_csrf_state = state_parts[0]
            user_id_for_storage = state_parts[1]
        elif len(state_parts) == 1:
            # If only one part, assume it's the user_id if CSRF state was not part of the initial construction
            # Or it could be just the CSRF state if user_id was not appended.
            # This logic relies on how get_authorization_url constructs the state.
            # For robustness, the frontend should consistently include both if both are used, or clearly one.
            # Assuming if user_id was sent to get_authorization_url, it's the last part or only part.
            user_id_for_storage = state_parts[-1] # Safely get the last part, which should be user_id if present

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
            response.raise_for_status()  # Raises an exception for 4XX/5XX responses
            token_data = response.json()

            # Add user_id to the token_data before storing, so backend knows who it belongs to.
            # The backend CincTokenController expects `user_id` in the body for `storeToken`.
            # It also expects `account_id` for CINC's own account ID, if available from token_data.
            storage_payload = {
                "user_id": user_id_for_storage,
                "access_token": token_data.get("access_token"),
                "refresh_token": token_data.get("refresh_token"),
                "expires_in": token_data.get("expires_in"),
                "account_id": token_data.get("account_id") # CINC's account_id, if provided
            }

            await store_cinc_tokens(user_id=user_id_for_storage, token_data=storage_payload)
            
            # Return the original token_data from CINC plus the user_id used for storage
            # so the callback in main.py can include user_id in the redirect to frontend.
            return {**token_data, "user_id_for_storage": user_id_for_storage, "original_csrf_state": original_csrf_state}
        except httpx.HTTPStatusError as e:
            error_detail = f"CINC token exchange failed: {e.response.status_code} - {e.response.text}"
            print(error_detail) # Log for server-side debugging
            raise HTTPException(status_code=e.response.status_code, detail=error_detail)
        except httpx.RequestError as e:
            error_detail = f"Request to CINC token endpoint failed: {str(e)}"
            print(error_detail) # Log for server-side debugging
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=error_detail)
        except Exception as e:
            error_detail = f"An unexpected error occurred during token exchange: {str(e)}"
            print(error_detail) # Log for server-side debugging
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=error_detail)

async def refresh_access_token(user_id_for_storage: str) -> Dict[str, Any]:
    """Refreshes the CINC access token using the stored refresh token and updates it via BackendHandler."""
    token_url = f"{CINC_AUTH_BASE_URL}/token" # Corrected base URL part
    
    current_tokens = await get_cinc_tokens(user_id_for_storage)
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

            await store_cinc_tokens(user_id=user_id_for_storage, token_data=storage_payload)
            
            # Return the new tokens (primarily the access token is of interest after refresh)
            return storage_payload # Or just {"access_token": new_token_data["access_token"], ...} as needed
        except httpx.HTTPStatusError as e:
            error_detail = f"CINC token refresh failed: {e.response.status_code} - {e.response.text}"
            print(error_detail)
            # If refresh fails (e.g. 400, 401), it might mean the refresh token is also invalid.
            # The user might need to re-authenticate.
            # Consider deleting the stored tokens or marking them as invalid.
            if e.response.status_code in [400, 401]:
                try:
                    await delete_cinc_tokens(user_id_for_storage) # Invalidate tokens on critical refresh failure
                except Exception as del_e:
                    print(f"Failed to delete tokens for user {user_id_for_storage} after refresh failure: {del_e}")
            raise HTTPException(status_code=e.response.status_code, detail=error_detail)
        except Exception as e:
            error_detail = f"Error during CINC token refresh: {str(e)}"
            print(error_detail)
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=error_detail)

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

async def get_leads(user_id: str, offset: int = 0, limit: int = 10, next_page: Optional[str] = None, from_lead_id: Optional[str] = None) -> Dict[str, Any]:
    endpoint = "/site/leads"
    params: Dict[str, Any] = {"offset": offset, "limit": limit} 
    if next_page:
        params["next"] = next_page
    if from_lead_id:
        params["from"] = f"id:{from_lead_id}"
    return await _make_cinc_request("GET", endpoint, user_id, params=params)

async def get_lead_details(user_id: str, lead_id: str, fields: Optional[List[str]] = None) -> Dict[str, Any]:    
    endpoint = f"/site/leads/{lead_id}"
    params: Dict[str, Any] = {} 
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

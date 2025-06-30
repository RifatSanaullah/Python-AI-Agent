import logging
import requests
import httpx
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any, List
import httpx
import requests

from fastapi import HTTPException, status
from app.config import settings
from app.services.backend_service import BackendHandler

CINC_AUTH_BASE_URL = "https://authv2.cincapi.com/integrator"
CINC_API_BASE_URL = "https://public.cincapi.com/v2"

_backend_handler = BackendHandler()

# Token cache to avoid database hits on every request
_token_cache = {}

def _get_cache_key(account_id: int, connection_id: Optional[str] = None) -> str:
    """Generate cache key for token storage"""
    return f"{account_id}_{connection_id or 'default'}"

def _is_token_expired(token_data: Dict[str, Any]) -> bool:
    """Check if cached token is expired"""
    try:
        cached_at = token_data.get("_cached_at")
        expires_in = token_data.get("expires_in")
        
        if not cached_at or not expires_in:
            return True
            
        # Add some buffer time (30 seconds) before actual expiration
        expiration_time = cached_at + timedelta(seconds=int(expires_in) - 30)
        return datetime.now(timezone.utc) >= expiration_time
    except Exception:
        return True

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
        
        # Cache the token after successful storage
        cache_key = _get_cache_key(account_id, token_data.get("connection_id"))
        cached_token = payload.copy()
        cached_token["_cached_at"] = datetime.now(timezone.utc)
        _token_cache[cache_key] = cached_token
        
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to store CINC token via backend: {str(e)}")

async def get_cinc_tokens(account_id: int, connection_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
    # Check cache first
    cache_key = _get_cache_key(account_id, connection_id)
    
    if cache_key in _token_cache:
        cached_token = _token_cache[cache_key]
        if not _is_token_expired(cached_token):
            return cached_token
        else:
            # Remove expired token from cache
            del _token_cache[cache_key]
    
    try:
        # Use connection_id if provided, otherwise fall back to account_id for lookup
        token_data = await _backend_handler.get_cinc_token_from_db(account_id, connection_id=connection_id)
        
        # Cache the token if found
        if token_data:
            cached_token = token_data.copy()
            cached_token["_cached_at"] = datetime.now(timezone.utc)
            _token_cache[cache_key] = cached_token
            
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
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error retrieving CINC tokens")

async def delete_cinc_tokens(account_id: int, connection_id: Optional[str] = None):
    try:
        await _backend_handler.delete_cinc_token_from_db(account_id, connection_id=connection_id)
        
        # Remove from cache as well
        cache_key = _get_cache_key(account_id, connection_id)
        if cache_key in _token_cache:
            del _token_cache[cache_key]
            
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to delete CINC token via backend: {str(e)}")

async def get_cinc_access_token(account_id: int, connection_id: Optional[str] = None) -> str:
    tokens = await get_cinc_tokens(account_id, connection_id=connection_id)
    if not tokens or not tokens.get("access_token"):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="CINC access token not found for account.")
    token_updated_at_str = tokens.get("updated_at")
    expires_in_seconds = tokens.get("expires_in")

    if not token_updated_at_str or expires_in_seconds is None:
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

async def register_cinc_webhook(access_token: str, connection_id: str):
    webhook_url = f"{settings.base_url}/new-cinc-lead"
    headers = {
        'Content-Type': 'application/json',
        'Authorization': access_token
    }

    data = {
        "url": webhook_url,
        "event_filters": ["lead.created"],
        "headers": {
            "X-Webhook-Secret": connection_id 
        }
    }
    try:
        response = requests.post(f"{CINC_API_BASE_URL}/site/webhook", headers=headers, json=data)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        return {"error": str(e)}

def get_authorization_url(state: Optional[str] = None, account_id: Optional[str] = None) -> str:
    auth_url = f"{CINC_AUTH_BASE_URL}/authorize" 
    composite_state_parts = []
    if state:
        composite_state_parts.append(state)
    if account_id:
        composite_state_parts.append(account_id)
    
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
    account_id_for_storage = None
    original_csrf_state = None 

    if composite_state:
        state_parts = composite_state.split("__")
        if len(state_parts) == 2:
            original_csrf_state = state_parts[0]
            account_id_for_storage = state_parts[1]
        elif len(state_parts) == 1:
            account_id_for_storage = state_parts[-1]

    if not account_id_for_storage:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Account ID could not be determined from state. Cannot store token.")

    payload = {
        'grant_type': 'authorization_code',
        'code': auth_code,
        'redirect_uri': settings.cinc_redirect_uri,
        'client_id': settings.cinc_client_id,
        'client_secret': settings.cinc_client_secret
    }

    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(token_url, data=payload)  # Debugging line
            response.raise_for_status()
            token_data = response.json()
            storage_payload = {
                "access_token": token_data.get("access_token"),
                "refresh_token": token_data.get("refresh_token"),
                "expires_in": token_data.get("expires_in"),
                "account_id": token_data.get("account_id") # 
            }

            # For OAuth flow, the account_id is passed directly from the state
            # In a real system, you might still need to validate the account_id
            try:
                account_id_int = int(account_id_for_storage)  # Convert to int for storage
            except ValueError:
                # If account_id is not a number, raise an error
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid account_id format for token storage")

            # Store tokens and get the connection_id from backend response
            backend_response = await _backend_handler.store_cinc_token_in_db(account_id=account_id_int, token_data=storage_payload)
            
            # Extract connection_id from backend response
            connection_id = None
            if isinstance(backend_response, dict):
                connection_id = backend_response.get("connection_id")
            
            # Update cache with the connection_id
            cache_key = _get_cache_key(account_id_int, connection_id)
            cached_token = storage_payload.copy()
            cached_token["connection_id"] = connection_id
            cached_token["_cached_at"] = datetime.now(timezone.utc)
            _token_cache[cache_key] = cached_token       
            # Register webhook after successful token storage using backend's connection_id
            if connection_id and token_data.get("access_token"):
                try:
                    webhook_result = await register_cinc_webhook(
                        access_token=token_data["access_token"], 
                        connection_id=connection_id
                    )
                    print(f"Webhook registration result: {webhook_result}")
                except Exception as webhook_error:
                    print(f"Failed to register webhook for connection_id {connection_id}: {webhook_error}")
                    # Don't fail the entire flow if webhook registration fails
            
            return {**token_data, "account_id_for_storage": account_id_for_storage, "original_csrf_state": original_csrf_state}
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



    async with httpx.AsyncClient(timeout=30.0) as client:
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

            response.raise_for_status()
            response_data = response.json()
            return response_data
        except httpx.TimeoutException as e:
            raise HTTPException(status_code=status.HTTP_504_GATEWAY_TIMEOUT, detail="CINC API request timed out")
        except httpx.ConnectError as e:
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Unable to connect to CINC API")
        except httpx.RequestError as e:
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="CINC API request failed")
        except httpx.HTTPStatusError as e:
            error_text = e.response.text
            raise HTTPException(status_code=e.response.status_code, detail=f"CINC API request error: {error_text}")
        except Exception as e:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to make CINC API request.")

async def get_leads(account_id: int, connection_id: Optional[str] = None, phone: Optional[str] = None) -> Dict[str, Any]:
    """Fetches leads from the CINC API, optionally filtering by phone."""
    endpoint = "/site/leads"
    query_params = {}
    if phone:
        query_params['info.contact.phone_numbers.cell_phone'] = phone
    
    response = await _make_cinc_request("GET", endpoint, account_id, connection_id=connection_id, params=query_params)
    
    if isinstance(response, dict) and "body" in response:
        return response["body"]
    return response

async def get_lead_details(account_id: int, lead_id: str, connection_id: Optional[str] = None, fields: Optional[List[str]] = None) -> Dict[str, Any]:    
    endpoint = f"/site/leads/{lead_id}"
    params = {}
    if fields:
        params["fields"] = ",".join(fields)
    
    response = await _make_cinc_request("GET", endpoint, account_id, connection_id=connection_id, params=params)
    
    # According to CINC API docs, the lead details are wrapped in a "lead" object within "body"
    if isinstance(response, dict):
        if "body" in response and "lead" in response["body"]:
            return response["body"]["lead"]
        elif "lead" in response:
            return response["lead"]
        elif "body" in response:
            return response["body"]
    
    # If no wrapper, return as-is
    return response

async def create_lead(account_id: int, lead_data: Dict[str, Any], connection_id: Optional[str] = None) -> Dict[str, Any]:    
    endpoint = "/site/leads"
    
    # Validate minimum required fields according to CINC API docs
    # The only required field is info.contact.email
    if not lead_data.get("info", {}).get("contact", {}).get("email"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail="CINC lead creation requires info.contact.email"
        )
    
    # Ensure proper structure for CINC API
    formatted_data = {
        "info": {
            "contact": {
                "email": lead_data["info"]["contact"]["email"]
            }
        }
    }
    
    # Notes should already be handled in call_handler.py, so we don't process Description here
    # This prevents duplicate notes from being created
    
    # Add optional fields if present
    contact = lead_data.get("info", {}).get("contact", {})
    
    # Add name fields
    if contact.get("first_name"):
        formatted_data["info"]["contact"]["first_name"] = contact["first_name"]
    if contact.get("last_name"):
        formatted_data["info"]["contact"]["last_name"] = contact["last_name"]
    
    # Add phone numbers
    if contact.get("phone_numbers"):
        formatted_data["info"]["contact"]["phone_numbers"] = contact["phone_numbers"]
    
    # Add mailing address
    if contact.get("mailing_address"):
        formatted_data["info"]["contact"]["mailing_address"] = contact["mailing_address"]
    
    # Add buyer/seller flags and data
    info = lead_data.get("info", {})
    if info.get("is_buyer") is not None:
        formatted_data["info"]["is_buyer"] = info["is_buyer"]
    if info.get("is_seller") is not None:
        formatted_data["info"]["is_seller"] = info["is_seller"]
    
    # Add buyer details
    if info.get("buyer"):
        formatted_data["info"]["buyer"] = info["buyer"]
    
    # Add seller details
    if info.get("seller"):
        formatted_data["info"]["seller"] = info["seller"]
    
    # Add source
    if info.get("source"):
        formatted_data["info"]["source"] = info["source"]
    
    # Add status
    if info.get("status"):
        formatted_data["info"]["status"] = info["status"]
    
    # Add secondary contact
    if info.get("secondary"):
        formatted_data["info"]["secondary"] = info["secondary"]
    
    # Add pipeline information
    if lead_data.get("pipeline"):
        formatted_data["pipeline"] = lead_data["pipeline"]
    
    # Add notes
    if lead_data.get("notes"):
        formatted_data["notes"] = lead_data["notes"]
    
    # Add assigned agents
    if lead_data.get("assigned_agents"):
        formatted_data["assigned_agents"] = lead_data["assigned_agents"]
    
    # Add registration date
    if lead_data.get("registered_date"):
        formatted_data["registered_date"] = lead_data["registered_date"]
    
    # Add created_by
    if lead_data.get("created_by"):
        formatted_data["created_by"] = lead_data["created_by"]
    
    # Add timezone
    if lead_data.get("timezone"):
        formatted_data["timezone"] = lead_data["timezone"]
    
    try:
        result = await _make_cinc_request("POST", endpoint, account_id, connection_id=connection_id, json_data=formatted_data)
        
        # CINC API wraps the response in "body" 
        if isinstance(result, dict) and "body" in result:
            return result["body"]
        return result
        
    except HTTPException as e:
        # Log the error details for debugging
        print(f"CINC lead creation failed for account {account_id}: {e.detail}")
        print(f"Data sent: {formatted_data}")
        raise e
    except Exception as e:
        print(f"Unexpected error creating CINC lead: {str(e)}")
        print(f"Data sent: {formatted_data}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
            detail=f"Failed to create CINC lead: {str(e)}"
        )

async def update_lead(account_id: int, lead_id: str, lead_data: Dict[str, Any], connection_id: Optional[str] = None) -> Dict[str, Any]:    
    endpoint = f"/site/leads/{lead_id}"
    try:
        existing_lead = await get_lead_details(account_id, lead_id, connection_id=connection_id)
        
        # Deep merge the new data with existing data
        def deep_merge(existing: Dict, updates: Dict) -> Dict:
            """Deep merge updates into existing data"""
            result = existing.copy()
            for key, value in updates.items():
                if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                    result[key] = deep_merge(result[key], value)
                else:
                    result[key] = value
            return result
        
        # Start with existing lead data and merge updates
        merged_payload = deep_merge(existing_lead, lead_data)
        
        # Ensure required fields for update
        merged_payload["id"] = lead_id
        
        # Ensure email is present (required by CINC)
        if "info" not in merged_payload:
            merged_payload["info"] = {}
        if "contact" not in merged_payload["info"]:
            merged_payload["info"]["contact"] = {}
        
        original_email = existing_lead.get("info", {}).get("contact", {}).get("email")
        if original_email:
            merged_payload["info"]["contact"]["email"] = original_email
        
    except Exception as e:
        # Fallback to original approach if we can't fetch existing data
        merged_payload = lead_data.copy()
        merged_payload["id"] = lead_id
    
    result = await _make_cinc_request("POST", endpoint, account_id, connection_id=connection_id, json_data=merged_payload)
    
    # CINC API wraps the response in "body" 
    if isinstance(result, dict) and "body" in result:
        final_result = result["body"]
    else:
        final_result = result
    
    # Add verification by fetching the lead after update to confirm changes
    try:
        updated_lead = await get_lead_details(account_id, lead_id, connection_id=connection_id)
        
        # Check if specific fields were updated (like budget)
        if 'info' in lead_data and 'buyer' in lead_data['info']:
            expected_budget = lead_data['info']['buyer'].get('average_price')
            actual_budget = updated_lead.get("info", {}).get("buyer", {}).get("average_price")
            
            if expected_budget is not None:
                if actual_budget != expected_budget:
                    # Log discrepancy but don't print debug info
                    pass
        
    except Exception as e:
        # Verification failed, but update may have succeeded
        pass
    
    return final_result

async def update_lead_via_upsert(account_id: int, lead_id: str, lead_data: Dict[str, Any], connection_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Alternative update method using the generic POST /site/leads endpoint (upsert functionality).
    According to CINC docs, this endpoint works as upsert - if ID is provided, it updates the lead.
    Use this method if the specific lead_id endpoint is not working properly.
    """
    endpoint = "/site/leads"
    
    # Notes should already be handled in call_handler.py, so we don't process Description here
    # This prevents duplicate notes from being created
    
    # Fetch existing lead and merge with updates for upsert as well
    try:
        existing_lead = await get_lead_details(account_id, lead_id, connection_id=connection_id)
        
        # Deep merge function (same as in update_lead)
        def deep_merge(existing: Dict, updates: Dict) -> Dict:
            """Deep merge updates into existing data"""
            result = existing.copy()
            for key, value in updates.items():
                if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                    result[key] = deep_merge(result[key], value)
                else:
                    result[key] = value
            return result
        
        # Merge updates with existing data
        upsert_payload = deep_merge(existing_lead, lead_data)
        upsert_payload["id"] = lead_id
        
        # Ensure email is present
        original_email = existing_lead.get("info", {}).get("contact", {}).get("email")
        if original_email:
            if "info" not in upsert_payload:
                upsert_payload["info"] = {}
            if "contact" not in upsert_payload["info"]:
                upsert_payload["info"]["contact"] = {}
            upsert_payload["info"]["contact"]["email"] = original_email
        
    except Exception as e:
        upsert_payload = lead_data.copy()
        upsert_payload["id"] = lead_id
    
    result = await _make_cinc_request("POST", endpoint, account_id, connection_id=connection_id, json_data=upsert_payload)
    
    # CINC API wraps the response in "body" 
    if isinstance(result, dict) and "body" in result:
        final_result = result["body"]
    else:
        final_result = result
    
    # Verify the update
    try:
        updated_lead = await get_lead_details(account_id, lead_id, connection_id=connection_id)
        
        if 'info' in lead_data and 'buyer' in lead_data['info']:
            expected_budget = lead_data['info']['buyer'].get('average_price')
            actual_budget = updated_lead.get("info", {}).get("buyer", {}).get("average_price")
            
            if expected_budget is not None:
                if actual_budget != expected_budget:
                    # Log discrepancy but don't print debug info
                    pass
        
    except Exception as e:
        # Verification failed, but upsert may have succeeded
        pass
    
    return final_result

async def get_leads_by_phone(account_id: int, phone: str, connection_id: Optional[str] = None) -> List[Dict[str, Any]]:
    try:
        # Clean phone number to match different formats
        clean_phone = ''.join(filter(str.isdigit, phone))
        
        if len(clean_phone) == 11 and clean_phone.startswith('1'):
            clean_phone = clean_phone[1:]  # Remove leading '1'
        elif len(clean_phone) == 10:
            pass  # Already in correct format
        else:
            print(f"Invalid phone number format: {phone}, treating as new call")
            pass
            # return []

        # Get leads from CINC using the actual cleaned phone number
        print(f"Fetching leads for phone number: {clean_phone}")
        leads_response = await get_leads(account_id, connection_id=connection_id, phone=clean_phone)
        leads_list = leads_response.get("leads", [])
        
        # Check if we have exactly one match - if not, treat as new call
        if len(leads_list) == 0:
            print(f"No leads found for phone number: {clean_phone}, treating as new call")
            return []
        elif len(leads_list) > 1:
            print(f"Multiple leads found for phone number: {clean_phone} (count: {len(leads_list)}), treating as new call")
            return []
        
        # Exactly one lead found - proceed with enriching it
        lead = leads_list[0]
        lead_id = lead.get('id')
        if lead_id:
            try:
                # Fetch notes for this lead
                notes = await get_lead_notes_with_content(account_id, lead_id, connection_id=connection_id)
                lead['notes'] = notes
            except Exception as e:
                print(f"Failed to fetch notes for lead {lead_id}: {e}")
                lead['notes'] = []
        else:
            lead['notes'] = []
        
        return [lead]  # Return single lead in a list for consistency
        
    except Exception as e:
        print(f"Error in get_leads_by_phone: {e}")
        return []

async def get_lead_notes(account_id: int, lead_id: str, connection_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """Fetch all notes for a specific lead from CINC API"""
    endpoint = f"/site/leads/{lead_id}/notes"
    try:
        response = await _make_cinc_request("GET", endpoint, account_id, connection_id=connection_id)
        if response and 'notes' in response:
            return response['notes']
        return []
    except Exception as e:
        return []

async def get_lead_note_content(account_id: int, note_id: str, connection_id: Optional[str] = None) -> Dict[str, Any]:
    """Fetch the content of a specific note from CINC API"""
    endpoint = f"/site/leads/notes/{note_id}"
    try:
        response = await _make_cinc_request("GET", endpoint, account_id, connection_id=connection_id)
        # Extract the note from the response body
        if response and 'note' in response:
            return response['note']
        return {}
    except Exception as e:
        return {}

async def get_lead_notes_with_content(account_id: int, lead_id: str, connection_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """Fetch all notes for a lead with their content"""
    import asyncio
    
    # First get the notes list (metadata only)
    notes = await get_lead_notes(account_id, lead_id, connection_id=connection_id)
    
    # Create tasks to fetch all note contents concurrently
    async def fetch_note_content_safe(note: Dict[str, Any]) -> Dict[str, Any]:
        note_id = note.get('id')
        if note_id:
            try:
                note_content = await get_lead_note_content(account_id, note_id, connection_id=connection_id)
                # Use the full note content which includes the content field
                if note_content:
                    return note_content
                else:
                    return note  # Keep note without content
            except Exception as e:
                return note  # Keep note without content
        else:
            return note  # Keep note without content
    
    # Execute all note content fetches concurrently
    tasks = [fetch_note_content_safe(note) for note in notes]
    notes_with_content = await asyncio.gather(*tasks)
    
    return notes_with_content


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

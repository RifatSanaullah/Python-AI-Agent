import logging
import requests
import httpx
import asyncio
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any, List

from fastapi import HTTPException, status
from app.config import settings
from app.services.backend_service import BackendHandler

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class CincService:
    """
    Unified CINC service class that handles OAuth, API calls, and webhooks.
    This class follows OOP principles to eliminate code duplication and improve maintainability.
    """
    
    def __init__(self):
        self.auth_base_url = "https://authv2.cincapi.com/integrator"
        self.api_base_url = "https://public.cincapi.com/v2"
        self.backend_handler = BackendHandler()
    
    # ==================== TOKEN MANAGEMENT ====================
    
    async def store_tokens(self, account_id: int, token_data: Dict[str, Any]) -> None:
        """Store CINC tokens in the backend."""
        payload = {
            "account_id": account_id,
            "access_token": token_data.get("access_token"),
            "refresh_token": token_data.get("refresh_token"),
            "expires_in": token_data.get("expires_in"),
            "connection_id": token_data.get("connection_id"),
        }
        
        # Check required fields, but be more flexible for refresh scenarios
        required_fields = ["account_id", "access_token", "refresh_token", "expires_in"]
        missing_fields = [field for field in required_fields if not payload.get(field)]
        
        if missing_fields:
            logger.error(f"Missing essential token data for storage: {missing_fields}. Payload: {payload}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, 
                detail=f"Missing essential token data for storage: {missing_fields}"
            )

        try:
            response = await self.backend_handler.store_cinc_token_in_db(account_id, payload)
            logger.info(f"CINC tokens stored successfully for account {account_id}")
            
            # Automatically register webhook after storing tokens
            try:
                # Check for connection_id in response first, then fallback to payload
                connection_id = response.get("connection_id") or payload.get("connection_id")
                if connection_id:
                    access_token = payload.get("access_token")
                    if access_token:
                        webhook_result = await self.register_webhook(access_token, connection_id)
                        logger.info(f"Webhook registration result: {webhook_result}")
                    else:
                        logger.warning(f"No access_token found for webhook registration")
                else:
                    logger.warning(f"No connection_id found in token response or payload, skipping webhook registration")
            except Exception as webhook_error:
                logger.error(f"Failed to register webhook after token storage: {webhook_error}")
                # Don't fail the token storage if webhook registration fails
            
            return response
        except HTTPException as e:
            logger.error(f"Backend error storing CINC tokens: {e.detail}")
            raise e
        except Exception as e:
            logger.error(f"Unexpected error storing CINC tokens: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to store CINC tokens"
            )

    async def get_tokens(self, account_id: int, connection_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Retrieve CINC tokens from backend."""
        try:
            response = await self.backend_handler.get_cinc_token_from_db(account_id, connection_id)
            return response
        except HTTPException as e:
            if e.status_code == 404:
                logger.info(f"No CINC tokens found for account {account_id}")
                return None
            logger.error(f"Backend error retrieving CINC tokens: {e.detail}")
            raise e
        except Exception as e:
            logger.error(f"Unexpected error retrieving CINC tokens: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to retrieve CINC tokens"
            )

    async def delete_tokens(self, account_id: int, connection_id: Optional[str] = None) -> None:
        """Delete CINC tokens from backend."""
        try:
            await self.backend_handler.delete_cinc_token_from_db(account_id, connection_id)
            logger.info(f"CINC tokens deleted for account {account_id}")
        except HTTPException as e:
            logger.error(f"Backend error deleting CINC tokens: {e.detail}")
            raise e
        except Exception as e:
            logger.error(f"Unexpected error deleting CINC tokens: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to delete CINC tokens"
            )

    async def get_access_token(self, account_id: int, connection_id: Optional[str] = None) -> str:
        """Get a valid access token, refreshing if necessary."""
        tokens = await self.get_tokens(account_id, connection_id=connection_id)
        if not tokens or not tokens.get("access_token"):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="No CINC access token found. User needs to re-authenticate."
            )

        # Check if token needs refresh
        if self._is_token_expired(tokens):
            logger.info(f"Access token expired for account {account_id}, refreshing...")
            try:
                refreshed_tokens = await self.refresh_access_token(account_id, connection_id)
                return refreshed_tokens["access_token"]
            except Exception as e:
                logger.error(f"Token refresh failed: {e}")
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Token refresh failed. User needs to re-authenticate."
                )

        return tokens["access_token"]

    def _is_token_expired(self, tokens: Dict[str, Any]) -> bool:
        """Check if token is expired based on timestamp and expires_in."""
        try:
            token_updated_at_str = tokens.get("updated_at")
            expires_in_seconds = tokens.get("expires_in")

            if not token_updated_at_str or expires_in_seconds is None:
                return True

            # Parse the timestamp
            token_updated_at = datetime.fromisoformat(token_updated_at_str.replace('Z', '+00:00'))
            
            # Add buffer time (30 seconds) before actual expiration
            expiration_time = token_updated_at + timedelta(seconds=int(expires_in_seconds) - 30)
            
            return datetime.now(timezone.utc) >= expiration_time
        except Exception as e:
            logger.error(f"Error checking token expiration: {e}")
            return True

    # ==================== OAUTH FLOW ====================

    def get_authorization_url(self, state: Optional[str] = None, account_id: Optional[str] = None) -> str:
        """Generate CINC OAuth authorization URL."""
        auth_url = f"{self.auth_base_url}/authorize"
        
        # Build composite state
        composite_state_parts = []
        if state:
            composite_state_parts.append(f"state:{state}")
        if account_id:
            composite_state_parts.append(f"account_id:{account_id}")
        
        final_composite_state = "__".join(composite_state_parts) if composite_state_parts else "default_state"

        params = {
            'client_id': settings.cinc_client_id,
            'response_type': 'code',
            'redirect_uri': settings.cinc_redirect_uri,
            'scope': 'api:read api:create api:update api:event',
            'state': final_composite_state
        }
        
        prepared_request = requests.Request('GET', auth_url, params=params).prepare()
        if prepared_request.url is None:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to generate authorization URL"
            )
        
        return prepared_request.url

    async def exchange_code_for_token(self, auth_code: str, composite_state: Optional[str]) -> Dict[str, Any]:
        """Exchange authorization code for access token."""
        token_url = f"{self.auth_base_url}/token"
        account_id_for_storage = None

        # Parse composite state
        if composite_state:
            state_parts = composite_state.split("__")
            for part in state_parts:
                if part.startswith("account_id:"):
                    account_id_for_storage = int(part.split(":", 1)[1])

        if not account_id_for_storage:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Account ID not found in state parameter"
            )

        payload = {
            'grant_type': 'authorization_code',
            'code': auth_code,
            'redirect_uri': settings.cinc_redirect_uri,
            'client_id': settings.cinc_client_id,
            'client_secret': settings.cinc_client_secret
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(token_url, data=payload)
            
            if response.status_code != 200:
                error_detail = response.text
                logger.error(f"Token exchange failed: {error_detail}")
                raise HTTPException(
                    status_code=response.status_code,
                    detail=f"Token exchange failed: {error_detail}"
                )
            
            token_data = response.json()
            
            # Prepare storage payload like the old code
            storage_payload = {
                "access_token": token_data.get("access_token"),
                "refresh_token": token_data.get("refresh_token"),
                "expires_in": token_data.get("expires_in"),
                "account_id": token_data.get("account_id"),  # CINC's own account_id
                "connection_id": token_data.get("connection_id")  # CINC's connection_id
            }
            
            # Store tokens
            await self.store_tokens(account_id_for_storage, storage_payload)
            
            return token_data

    async def refresh_access_token(self, account_id: int, connection_id: Optional[str] = None) -> Dict[str, Any]:
        """Refresh CINC access token using refresh token."""
        token_url = f"{self.auth_base_url}/token"
        
        current_tokens = await self.get_tokens(account_id, connection_id=connection_id)
        if not current_tokens or not current_tokens.get("refresh_token"):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="No refresh token available. User needs to re-authenticate."
            )

        payload = {
            'grant_type': 'refresh_token',
            'refresh_token': current_tokens["refresh_token"],
            'client_id': settings.cinc_client_id,
            'client_secret': settings.cinc_client_secret
        }

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
                    "connection_id": current_tokens.get("connection_id") # Preserve connection_id
                }
                
                # If CINC returns a new refresh token, use it. Otherwise, keep the old one
                if not storage_payload["refresh_token"]:
                    storage_payload["refresh_token"] = current_tokens["refresh_token"] # Keep old if not in new response

                await self.store_tokens(account_id, storage_payload) # account_id is the key for storing
                return storage_payload  # Return the storage_payload which has all required fields
                
            except httpx.HTTPStatusError as e:
                error_detail = f"CINC token refresh failed: {e.response.status_code} - {e.response.text}"
                logger.error(error_detail)
                # If refresh fails (e.g. 400, 401), it might mean the refresh token is also invalid.
                if e.response.status_code in [400, 401]:
                    try:
                        await self.delete_tokens(account_id, connection_id=connection_id)
                    except Exception as del_e:
                        logger.error(f"Failed to delete tokens for account {account_id} after refresh failure: {del_e}")
                raise HTTPException(status_code=e.response.status_code, detail=error_detail)
            except Exception as e:
                error_detail = f"Error during CINC token refresh: {str(e)}"
                logger.error(error_detail)
                raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=error_detail)

    # ==================== API REQUESTS ====================

    async def _make_api_request(
        self, 
        method: str, 
        endpoint: str, 
        account_id: int, 
        connection_id: Optional[str] = None, 
        params: Optional[Dict[str, Any]] = None, 
        json_data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Make authenticated API request to CINC."""
        access_token = await self.get_access_token(account_id, connection_id=connection_id)
        
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        
        url = f"{self.api_base_url}{endpoint}"

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.request(
                method=method,
                url=url,
                headers=headers,
                params=params,
                json=json_data
            )
            
            if response.status_code not in [200, 201]:
                error_detail = response.text
                logger.error(f"CINC API request failed: {method} {endpoint} - {error_detail}")
                raise HTTPException(
                    status_code=response.status_code,
                    detail=f"CINC API request failed: {error_detail}"
                )
            
            return response.json()

    # ==================== LEAD MANAGEMENT ====================

    async def get_leads(
        self, 
        account_id: int, 
        connection_id: Optional[str] = None, 
        phone: Optional[str] = None
    ) -> Dict[str, Any]:
        """Fetch leads from CINC API, optionally filtering by phone."""
        endpoint = "/site/leads"
        query_params = {}
        
        if phone:
            # Clean phone number to match different formats
            clean_phone = ''.join(filter(str.isdigit, phone))
            
            if len(clean_phone) == 11 and clean_phone.startswith('1'):
                clean_phone = clean_phone[1:]  # Remove leading '1'
            elif len(clean_phone) == 10:
                pass  # Already in correct format
            else:
                logger.warning(f"Invalid phone number format: {phone}, using as-is")
                clean_phone = phone
            
            query_params["info.contact.phone_numbers.cell_phone"] = clean_phone
        
        response = await self._make_api_request(
            "GET", endpoint, account_id, connection_id=connection_id, params=query_params
        )
        
        # Extract leads from response body if wrapped
        if isinstance(response, dict) and "body" in response:
            return response["body"]
        
        return response

    async def get_lead_details(
        self, 
        account_id: int, 
        lead_id: str, 
        connection_id: Optional[str] = None, 
        fields: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Get detailed information for a specific lead."""
        endpoint = f"/site/leads/{lead_id}"
        params = {}
        
        if fields:
            params["fields"] = ",".join(fields)
        
        response = await self._make_api_request(
            "GET", endpoint, account_id, connection_id=connection_id, params=params
        )
        
        # Just return the raw response - let the caller handle the data structure
        return response

    async def create_lead(
        self, 
        account_id: int, 
        lead_data: Dict[str, Any], 
        connection_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Create a new lead in CINC."""
        endpoint = "/site/leads"
        
        # Validate required fields
        if not lead_data.get("info", {}).get("contact", {}).get("email"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email is required to create a lead"
            )
        
        # Format data for CINC API
        formatted_data = self._format_lead_data(lead_data)
        
        try:
            response = await self._make_api_request(
                "POST", endpoint, account_id, connection_id=connection_id, json_data=formatted_data
            )
            
            logger.info(f"Lead created successfully for account {account_id}")
            return response
        except HTTPException as e:
            logger.error(f"Failed to create lead: {e.detail}")
            raise e
        except Exception as e:
            logger.error(f"Unexpected error creating lead: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create lead"
            )

    async def update_lead(
        self, 
        account_id: int, 
        lead_id: str, 
        lead_data: Dict[str, Any], 
        connection_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Update an existing lead in CINC."""
        endpoint = f"/site/leads/{lead_id}"
        
        try:
            # Get current lead data and merge with updates
            current_lead = await self.get_lead_details(account_id, lead_id, connection_id)
            merged_payload = self._merge_lead_data(current_lead, lead_data)
            
            result = await self._make_api_request(
                "POST", endpoint, account_id, connection_id=connection_id, json_data=merged_payload
            )
            
            # Extract result from response body if wrapped
            if isinstance(result, dict) and "body" in result:
                final_result = result["body"]
            else:
                final_result = result
            
            logger.info(f"Lead {lead_id} updated successfully")
            return final_result
            
        except Exception as e:
            logger.error(f"Failed to update lead {lead_id}: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to update lead: {str(e)}"
            )

    def _format_lead_data(self, lead_data: Dict[str, Any]) -> Dict[str, Any]:
        """Format lead data for CINC API requirements."""
        formatted_data = {
            "info": {
                "contact": {
                    "email": lead_data["info"]["contact"]["email"]
                }
            }
        }
        
        # Add optional contact fields
        contact = lead_data.get("info", {}).get("contact", {})
        
        if contact.get("first_name"):
            formatted_data["info"]["contact"]["first_name"] = contact["first_name"]
        if contact.get("last_name"):
            formatted_data["info"]["contact"]["last_name"] = contact["last_name"]
        if contact.get("phone_numbers"):
            formatted_data["info"]["contact"]["phone_numbers"] = contact["phone_numbers"]
        if contact.get("mailing_address"):
            formatted_data["info"]["contact"]["mailing_address"] = contact["mailing_address"]
        
        # Add other optional fields
        info = lead_data.get("info", {})
        if info.get("is_buyer") is not None:
            formatted_data["info"]["is_buyer"] = info["is_buyer"]
        if info.get("is_seller") is not None:
            formatted_data["info"]["is_seller"] = info["is_seller"]
        if info.get("buyer"):
            formatted_data["info"]["buyer"] = info["buyer"]
        if info.get("seller"):
            formatted_data["info"]["seller"] = info["seller"]
        if info.get("source"):
            formatted_data["info"]["source"] = info["source"]
        if info.get("status"):
            formatted_data["info"]["status"] = info["status"]
        if info.get("secondary"):
            formatted_data["info"]["secondary"] = info["secondary"]
        
        # Add pipeline, notes, etc.
        if lead_data.get("pipeline"):
            formatted_data["pipeline"] = lead_data["pipeline"]
        if lead_data.get("notes"):
            formatted_data["notes"] = lead_data["notes"]
        if lead_data.get("assigned_agents"):
            formatted_data["assigned_agents"] = lead_data["assigned_agents"]
        if lead_data.get("registered_date"):
            formatted_data["registered_date"] = lead_data["registered_date"]
        if lead_data.get("created_by"):
            formatted_data["created_by"] = lead_data["created_by"]
        if lead_data.get("timezone"):
            formatted_data["timezone"] = lead_data["timezone"]
        
        return formatted_data

    def _merge_lead_data(self, current_lead: Dict[str, Any], updates: Dict[str, Any]) -> Dict[str, Any]:
        """Merge current lead data with updates."""
        # Deep copy current lead and update with new data
        merged = current_lead.copy()
        
        # Handle nested updates properly
        for key, value in updates.items():
            if key in merged and isinstance(merged[key], dict) and isinstance(value, dict):
                merged[key].update(value)
            else:
                merged[key] = value
        
        return merged

    # ==================== AGENT MANAGEMENT ====================

    async def get_agent(
        self, 
        account_id: int, 
        agent_id: str, 
        connection_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get agent information by agent ID."""
        endpoint = f"/site/agents/{agent_id}"
        
        try:
            response = await self._make_api_request(
                "GET", endpoint, account_id, connection_id=connection_id
            )
            
            # Extract agent from response body if wrapped
            if isinstance(response, dict) and "body" in response:
                return response["body"]
            
            return response
            
        except Exception as e:
            logger.error(f"Failed to get agent {agent_id}: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to retrieve agent information: {str(e)}"
            )

    # ==================== WEBHOOK MANAGEMENT ====================

    async def register_webhook(self, access_token: str, connection_id: str) -> Dict[str, Any]:
        """Register webhook with CINC for lead events."""
        webhook_url = f"{settings.base_url}/new-cinc-lead"
        headers = {
            'Content-Type': 'application/json',
            'Authorization': access_token
        }

        data = {
            "url": webhook_url,
            "event_filters": [
                "lead.created",
                "{event.type == 'agent.communications.received' && (event.communication.origin.is_ai == true && event.communication.origin.is_reply == true)}"
            ],
            "headers": {
                "X-Webhook-Secret": connection_id
            }
        }
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.api_base_url}/site/webhook",
                    headers=headers,
                    json=data
                )
                
                if response.status_code not in [200, 201]:
                    raise HTTPException(
                        status_code=response.status_code,
                        detail=f"Failed to register webhook: {response.text}"
                    )
                
                logger.info(f"Webhook registered successfully for connection {connection_id}")
                return response.json()
        except Exception as e:
            logger.error(f"Failed to register webhook: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to register webhook: {str(e)}"
            )



    # ==================== UTILITY METHODS ====================

    async def get_pipeline_by_phone(
        self, 
        account_id: int, 
        phone: str, 
        connection_id: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """Get lead pipeline info by phone number - simple and fast."""
        print(f"Looking up pipeline for phone: {phone}")
        try:
            # Clean phone number
            clean_phone = ''.join(filter(str.isdigit, phone))
            
            if len(clean_phone) == 11 and clean_phone.startswith('1'):
                clean_phone = clean_phone[1:]  # Remove leading '1'
            elif len(clean_phone) == 10:
                pass  # Already in correct format
            else:
                logger.warning(f"Invalid phone number format: {phone}, using as-is")
                clean_phone = phone
            
            logger.info(f"Fetching pipeline for phone: {clean_phone}")
            print(f"Fetching leads for cleaned phone number: {clean_phone}")
            # Get leads by phone
            response = await self.get_leads(account_id, connection_id, phone=clean_phone)
            print(f"Basic leads response: {response}")
            
            # Extract leads array from response
            leads_list = []
            if isinstance(response, dict) and "leads" in response:
                leads_list = response["leads"]
            elif isinstance(response, list):
                leads_list = response
            
            if not leads_list or len(leads_list) == 0:
                logger.info(f"No leads found for phone: {clean_phone}")
                return None
            
            # Get the most recent lead ID
            lead = leads_list[-1]
            lead_id = lead.get('id')
            
            if not lead_id:
                logger.warning(f"No lead ID found for phone: {clean_phone}")
                return None
            
            print(f"Found lead {lead_id}, fetching detailed information...")
            
            # Fetch detailed lead information including pipeline
            detailed_lead = await self.get_lead_details(account_id, lead_id, connection_id)
            lead_data = detailed_lead.get('lead', detailed_lead)
            pipeline = lead_data.get('pipeline', {})
            
            print(f"Detailed lead {lead_id} with pipeline: {pipeline}")
            
            # Return lead information with pipeline data
            result = {
                'lead_id': lead_id,
                'pipeline': pipeline,
                'lead_exists': True,
                'stage': pipeline.get('stage') if pipeline else None,
                'history': pipeline.get('history', []) if pipeline else []
            }
            
            logger.info(f"Returning pipeline info for lead {lead_id}: {result}")
            return result
            
        except Exception as e:
            logger.error(f"Error fetching pipeline for phone {phone}: {e}")
            return None

    async def get_leads_by_phone(
        self, 
        account_id: int, 
        phone: str, 
        connection_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Get leads filtered by phone number."""
        # Clean phone number to match different formats
        clean_phone = ''.join(filter(str.isdigit, phone))
        
        if len(clean_phone) == 11 and clean_phone.startswith('1'):
            clean_phone = clean_phone[1:]  # Remove leading '1'
        elif len(clean_phone) == 10:
            pass  # Already in correct format
        else:
            logger.warning(f"Invalid phone number format: {phone}, using as-is")
        
        logger.info(f"Fetching leads for cleaned phone number: {clean_phone}")
        response = await self.get_leads(account_id, connection_id, phone=clean_phone)
        
        # Extract leads array from response
        leads_list = []
        if isinstance(response, dict) and "leads" in response:
            leads_list = response["leads"]
        elif isinstance(response, list):
            leads_list = response
        
        # Check if we have exactly one match - if not, treat as new call
        if len(leads_list) == 0:
            logger.info(f"No leads found for phone number: {clean_phone}, treating as new call")
            return []
        elif len(leads_list) > 1:
            logger.info(f"Multiple leads found for phone number: {clean_phone} (count: {len(leads_list)}), treating as new call")
            # Note: In old code, this would return [] but we'll process the last lead
        
        # Process the last lead (or only lead) and enrich it with notes
        lead = leads_list[-1]  # Get the last/most recent lead
        lead['routing_phone'] = None
        created_by_agent_id = lead.get("assigned_agents",{}).get("primary_agent",{}).get("id")
        if created_by_agent_id:
                agent_data = await self.get_agent(account_id, created_by_agent_id, connection_id)
                agent_home_phone = agent_data.get('agent', agent_data)['info']['contact']['phone_numbers']['home_phone']
                lead['routing_phone'] = agent_home_phone
        lead_id = lead.get('id')
        if lead_id:
            try:
                # Fetch notes for this lead (this was missing in the new code!)
                notes = await self.get_lead_notes_with_content(account_id, lead_id, connection_id=connection_id)
                lead['notes'] = notes
                logger.info(f"Enriched lead {lead_id} with {len(notes)} notes")
            except Exception as e:
                logger.error(f"Failed to fetch notes for lead {lead_id}: {e}")
                lead['notes'] = []
        else:
            lead['notes'] = []
        
        return [lead]  # Return single lead in a list for consistency

    async def get_lead_notes(
        self, 
        account_id: int, 
        lead_id: str, 
        connection_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Get notes for a specific lead."""
        endpoint = f"/site/leads/{lead_id}/notes"
        
        response = await self._make_api_request(
            "GET", endpoint, account_id, connection_id=connection_id
        )
        
        if isinstance(response, dict) and "body" in response:
            return response["body"].get("notes", [])
        
        return response.get("notes", []) if isinstance(response, dict) else []

    async def get_lead_note_content(
        self, 
        account_id: int, 
        note_id: str, 
        connection_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get content for a specific note."""
        endpoint = f"/site/leads/notes/{note_id}"
        
        try:
            response = await self._make_api_request(
                "GET", endpoint, account_id, connection_id=connection_id
            )
            
            # Extract the note from response body if wrapped
            if isinstance(response, dict) and "note" in response:
                return response["note"]
            elif isinstance(response, dict) and "body" in response and "note" in response["body"]:
                return response["body"]["note"]
            
            return response if isinstance(response, dict) else {}
        except Exception as e:
            logger.error(f"Failed to get note content {note_id}: {e}")
            return {}

    async def get_lead_notes_with_content(
        self, 
        account_id: int, 
        lead_id: str, 
        connection_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Get all notes for a lead with their full content."""
        # First get the notes list (metadata only)
        notes = []
        # notes = await self.get_lead_notes(account_id, lead_id, connection_id=connection_id)
        
        # Create tasks to fetch all note contents concurrently
        async def fetch_note_content_safe(note: Dict[str, Any]) -> Optional[Dict[str, Any]]:
            note_id = note.get('id')
            if note_id:
                try:
                    note_content = await self.get_lead_note_content(account_id, note_id, connection_id=connection_id)
                    # Use the full note content which includes the content field
                    if note_content:
                        # Filter out notes that start with "Call Logs:"
                        content = note_content.get('content', '')
                        if content and content.strip().startswith('Call Logs:'):
                            logger.info(f"Filtering out call logs note {note_id}")
                            return None  # Filter out this note
                        return note_content
                    else:
                        return note  # Keep note without content
                except Exception as e:
                    logger.warning(f"Failed to fetch content for note {note_id}: {e}")
                    return note  # Keep note without content
            else:
                return note  # Keep note without content
        
        # Execute all note content fetches concurrently
        tasks = [fetch_note_content_safe(note) for note in notes]
        notes_with_content_raw = await asyncio.gather(*tasks)
        
        # Filter out None values (filtered call logs notes)
        notes_with_content = [note for note in notes_with_content_raw if note is not None]
        
        return notes_with_content

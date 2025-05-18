import json
import logging
from typing import Dict, Any, Optional, List
from app.services.nango_service import NangoService

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("salesforce_service")

class SalesforceService(NangoService):
    def __init__(self):
        super().__init__()
        logger.info("SalesforceService initialized")
    
    async def get_accounts(self, connection_id: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        logger.info(f"Fetching Salesforce accounts with connection_id: {connection_id}")
        try:
            result = await self.fetch_data(connection_id, "accounts", params, 'salesforce')
            logger.info(f"Successfully fetched {len(result.get('data', []))} Salesforce accounts")
            return result
        except Exception as e:
            logger.error(f"Error fetching Salesforce accounts: {str(e)}")
            raise
    
    async def get_account_by_id(self, connection_id: str, account_id: str) -> Dict[str, Any]:
        params = {"id": account_id}
        return await self.fetch_data(connection_id, "get-account-by-id", params, 'salesforce')
    
    async def get_contacts(self, connection_id: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        return await self.fetch_data(connection_id, "contacts", params, 'salesforce')
    
    async def get_contact_by_id(self, connection_id: str, contact_id: str) -> Dict[str, Any]:
        params = {"id": contact_id}
        return await self.fetch_data(connection_id, "get-contact-by-id", params, 'salesforce')
    
    async def get_leads(self, connection_id: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        return await self.fetch_data(connection_id, "leads", params, 'salesforce')
    
    async def get_lead_by_id(self, connection_id: str, lead_id: str) -> Dict[str, Any]:
        params = {"id": lead_id}
        return await self.fetch_data(connection_id, "get-lead-by-id", params, 'salesforce')
    
    async def get_opportunities(self, connection_id: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        return await self.fetch_data(connection_id, "opportunities", params, 'salesforce')
    
    async def get_opportunity_by_id(self, connection_id: str, opportunity_id: str) -> Dict[str, Any]:
        params = {"id": opportunity_id}
        return await self.fetch_data(connection_id, "get-opportunity-by-id", params, 'salesforce')
    
    async def get_cases(self, connection_id: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        return await self.fetch_data(connection_id, "get-cases", params, 'salesforce')
    
    async def get_case_by_id(self, connection_id: str, case_id: str) -> Dict[str, Any]:
        params = {"id": case_id}
        return await self.fetch_data(connection_id, "get-case-by-id", params, 'salesforce')
    
    async def get_products(self, connection_id: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        return await self.fetch_data(connection_id, "get-products", params, 'salesforce')
    
    async def get_product_by_id(self, connection_id: str, product_id: str) -> Dict[str, Any]:
        params = {"id": product_id}
        return await self.fetch_data(connection_id, "get-product-by-id", params, 'salesforce')
    
    async def get_users(self, connection_id: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        return await self.fetch_data(connection_id, "get-users", params, 'salesforce')
    
    async def get_user_by_id(self, connection_id: str, user_id: str) -> Dict[str, Any]:
        params = {"id": user_id}
        return await self.fetch_data(connection_id, "get-user-by-id", params, 'salesforce')
    
    async def get_campaigns(self, connection_id: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        return await self.fetch_data(connection_id, "get-campaigns", params, 'salesforce')
    
    async def get_campaign_by_id(self, connection_id: str, campaign_id: str) -> Dict[str, Any]:
        params = {"id": campaign_id}
        return await self.fetch_data(connection_id, "get-campaign-by-id", params, 'salesforce')
    
    async def get_contact_by_phone(self, connection_id: str, phone: str) -> Dict[str, Any]:
        params = {"phone": phone}
        return await self.post_data(connection_id, "get-contact", params, 'salesforce')
    
    async def get_lead_by_phone(self, connection_id: str, phone: str) -> Dict[str, Any]:
        params = {"phone": phone}
        return await self.post_data(connection_id, "get-lead", params, 'salesforce')
    
    async def store_contacts(self, connection_id: str, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        return await self.post_data(connection_id, "contact", payload, 'salesforce')
    
    async def update_contacts(self, connection_id: str, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        return await self.post_data(connection_id, "contacts", payload, 'salesforce', True)
    
    async def update_leads(self, connection_id: str, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        return await self.post_data(connection_id, "leads", payload, 'salesforce', True)
    
    async def store_leads(self, connection_id: str, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        return await self.post_data(connection_id, "create-lead", payload, 'salesforce')
    
    async def create_event(self, connection_id: str, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        return await self.post_data(connection_id, "create-event", payload, 'salesforce')
    
    async def update_event(self, connection_id: str, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        return await self.post_data(connection_id, "update-event", payload, 'salesforce' , True)
    
    async def delete_event(self, connection_id: str, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        return await self.delete_data(connection_id, "delete-event", payload, 'salesforce')

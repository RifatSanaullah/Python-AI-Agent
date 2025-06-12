import json
import logging
from typing import Dict, Any, Optional, List
from app.services.nango_service import NangoService

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("zoho_service")

class ZohoService(NangoService):
    def __init__(self):
        super().__init__()
        logger.info("ZohoService initialized")
        
    
    async def get_contacts(self, connection_id: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        logger.info(f"Fetching Zoho contacts with connection_id: {connection_id}")
        try:
            result = await self.fetch_data(connection_id, "zoho-crm/contacts", params, 'zoho-crm')
            logger.info(f"Successfully fetched {len(result.get('data', []))} Zoho contacts")
            return result
        except Exception as e:
            logger.error(f"Error fetching Zoho contacts: {str(e)}")
            raise
    
    async def get_contact_by_id(self, connection_id: str, contact_id: str) -> Dict[str, Any]:
        params = {"id": contact_id}
        return await self.fetch_data(connection_id, "get-contact-by-id", params, 'zoho-crm')
    
    async def get_accounts(self, connection_id: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        return await self.fetch_data(connection_id, "zoho-crm/accounts", params, 'zoho-crm')
    
    async def get_account_by_id(self, connection_id: str, account_id: str) -> Dict[str, Any]:
        params = {"id": account_id}
        return await self.fetch_data(connection_id, "get-account-by-id", params, 'zoho-crm')
    
    async def get_leads(self, connection_id: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        return await self.fetch_data(connection_id, "get-leads", params, 'zoho-crm')
    
    async def get_lead_by_id(self, connection_id: str, lead_id: str) -> Dict[str, Any]:
        params = {"id": lead_id}
        return await self.fetch_data(connection_id, "get-lead-by-id", params, 'zoho-crm')
    
    async def get_deals(self, connection_id: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        return await self.fetch_data(connection_id, "get-deals", params, 'zoho-crm')
    
    async def get_deal_by_id(self, connection_id: str, deal_id: str) -> Dict[str, Any]:
        params = {"id": deal_id}
        return await self.fetch_data(connection_id, "get-deal-by-id", params, 'zoho-crm')
    
    async def get_products(self, connection_id: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        
        return await self.fetch_data(connection_id, "get-products", params, 'zoho-crm')
    
    async def get_product_by_id(self, connection_id: str, product_id: str) -> Dict[str, Any]:
        
        params = {"id": product_id}
        return await self.fetch_data(connection_id, "get-product-by-id", params, 'zoho-crm')
    
    async def get_users(self, connection_id: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        
        return await self.fetch_data(connection_id, "get-users", params, 'zoho-crm')
    
    async def get_user_by_id(self, connection_id: str, user_id: str) -> Dict[str, Any]:
       
        params = {"id": user_id}
        return await self.fetch_data(connection_id, "get-user-by-id", params, 'zoho-crm')
    
    async def update_leads(self, connection_id: str, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        return await self.post_data(connection_id, "update-lead", payload, 'zoho-crm', True)
    
    async def store_leads(self, connection_id: str, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        return await self.post_data(connection_id, "create-lead", payload, 'zoho-crm')
    
    async def get_lead_by_phone(self, connection_id: str, phone: str) -> Dict[str, Any]:
        params = {"phone": phone}
        return await self.post_data(connection_id, "get-lead", params, 'zoho-crm')
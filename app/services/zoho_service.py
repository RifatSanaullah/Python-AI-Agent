import json
from typing import Dict, Any, Optional, List
from app.services.nango_service import NangoService

class ZohoService(NangoService):
    
    async def get_contacts(self, connection_id: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
       
        return await self.fetch_data(connection_id, "get-contacts", params)
    
    async def get_contact_by_id(self, connection_id: str, contact_id: str) -> Dict[str, Any]:
        params = {"id": contact_id}
        return await self.fetch_data(connection_id, "get-contact-by-id", params)
    
    async def get_accounts(self, connection_id: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        return await self.fetch_data(connection_id, "get-accounts", params)
    
    async def get_account_by_id(self, connection_id: str, account_id: str) -> Dict[str, Any]:
        params = {"id": account_id}
        return await self.fetch_data(connection_id, "get-account-by-id", params)
    
    async def get_leads(self, connection_id: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        return await self.fetch_data(connection_id, "get-leads", params)
    
    async def get_lead_by_id(self, connection_id: str, lead_id: str) -> Dict[str, Any]:
        params = {"id": lead_id}
        return await self.fetch_data(connection_id, "get-lead-by-id", params)
    
    async def get_deals(self, connection_id: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        return await self.fetch_data(connection_id, "get-deals", params)
    
    async def get_deal_by_id(self, connection_id: str, deal_id: str) -> Dict[str, Any]:
        params = {"id": deal_id}
        return await self.fetch_data(connection_id, "get-deal-by-id", params)
    
    async def get_products(self, connection_id: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        
        return await self.fetch_data(connection_id, "get-products", params)
    
    async def get_product_by_id(self, connection_id: str, product_id: str) -> Dict[str, Any]:
        
        params = {"id": product_id}
        return await self.fetch_data(connection_id, "get-product-by-id", params)
    
    async def get_users(self, connection_id: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        
        return await self.fetch_data(connection_id, "get-users", params)
    
    async def get_user_by_id(self, connection_id: str, user_id: str) -> Dict[str, Any]:
       
        params = {"id": user_id}
        return await self.fetch_data(connection_id, "get-user-by-id", params)
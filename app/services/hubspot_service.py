import json
import logging
from typing import Dict, Any, Optional, List
from app.services.nango_service import NangoService

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("hubspot_service")

class HubSpotService(NangoService):
    def __init__(self):
        super().__init__()
        logger.info("HubSpotService initialized")
    
    async def get_all_contacts(self, connection_id: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        logger.info(f"Fetching HubSpot contacts with connection_id: {connection_id}")
        try:
            result = await self.fetch_data(connection_id, "get-all-contacts", params)
            logger.info(f"Successfully fetched HubSpot contacts: {len(result.get('data', []))} contacts found")
            return result
        except Exception as e:
            logger.error(f"Error fetching HubSpot contacts: {str(e)}")
            raise
    
    async def get_contact_by_id(self, connection_id: str, contact_id: str) -> Dict[str, Any]:
        params = {"id": contact_id}
        return await self.fetch_data(connection_id, "get-contact-by-id", params)
    
    async def get_recent_contacts(self, connection_id: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        return await self.fetch_data(connection_id, "get-recent-contacts", params)
    
    async def get_all_companies(self, connection_id: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        return await self.fetch_data(connection_id, "get-all-companies", params)
    
    async def get_company_by_id(self, connection_id: str, company_id: str) -> Dict[str, Any]:
        params = {"id": company_id}
        return await self.fetch_data(connection_id, "get-company-by-id", params)
    
    async def get_deals(self, connection_id: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        return await self.fetch_data(connection_id, "get-deals", params)
    
    async def get_deal_by_id(self, connection_id: str, deal_id: str) -> Dict[str, Any]:
        params = {"id": deal_id}
        return await self.fetch_data(connection_id, "get-deal-by-id", params)
    
    async def get_tickets(self, connection_id: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        return await self.fetch_data(connection_id, "get-tickets", params)
    
    async def get_ticket_by_id(self, connection_id: str, ticket_id: str) -> Dict[str, Any]:
        params = {"id": ticket_id}
        return await self.fetch_data(connection_id, "get-ticket-by-id", params)
    
    async def get_line_items(self, connection_id: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        return await self.fetch_data(connection_id, "get-line-items", params)
    
    async def get_line_item_by_id(self, connection_id: str, line_item_id: str) -> Dict[str, Any]:
        params = {"id": line_item_id}
        return await self.fetch_data(connection_id, "get-line-item-by-id", params)
    
    # async def get_products(self, connection_id: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    #     return await self.fetch_data(connection_id, "get-products", params)
    
    # async def get_product_by_id(self, connection_id: str, product_id: str) -> Dict[str, Any]:
    #     params = {"id": product_id}
    #     return await self.fetch_data(connection_id, "get-product-by-id", params)
    
    async def get_owners(self, connection_id: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        return await self.fetch_data(connection_id, "get-owners", params)
    
    async def get_owner_by_id(self, connection_id: str, owner_id: str) -> Dict[str, Any]:
        params = {"id": owner_id}
        return await self.fetch_data(connection_id, "get-owner-by-id", params)
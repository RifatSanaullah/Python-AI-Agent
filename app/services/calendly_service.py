import json
import logging
from typing import Dict, Any, Optional, List
from app.services.nango_service import NangoService

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("calendly_service")

class CalendlyService(NangoService):
    def __init__(self):
        super().__init__()
        logger.info("CalendlyService initialized")
    
    async def get_user(self, connection_id: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:

        logger.info(f"Fetching Calendly user with connection_id: {connection_id}")
        try:
            result = await self.fetch_data(connection_id, "users", params, 'calendly')
            logger.info(f"Successfully fetched Calendly user")
            return result
        except Exception as e:
            logger.error(f"Error fetching Calendly user: {str(e)}")
            raise

    async def get_events(self, connection_id: str) -> Dict[str, Any]:

        logger.info(f"Fetching Calendly events with connection_id: {connection_id}")
        try:
            result = await self.fetch_data(connection_id, "events", None, 'calendly')
            logger.info(f"Successfully fetched Calendly events")
            return result
        except Exception as e:
            logger.error(f"Error fetching Calendly events: {str(e)}")
            raise

import json
import logging
import requests
from typing import Dict, Any, Optional, List
from app.services.nango_service import NangoService

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("outlook_calendar_service")

class OutlookCalendarService(NangoService):
    def __init__(self):
        super().__init__()
        logger.info("OutlookCalendarService initialized")
    
    async def get_calendars(self, connection_id: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        logger.info(f"Fetching Outlook calendars with connection_id: {connection_id}")
        try:
            # Using the Nango API to fetch calendars from Microsoft Graph API
            result = await self.fetch_data(connection_id, "calendars", params, 'outlook')
            logger.info(f"Successfully fetched Outlook calendars")
            return result
        except Exception as e:
            logger.error(f"Error fetching Outlook calendars: {str(e)}")
            raise
    
    async def get_events(self, connection_id: str, calendar_id: Optional[str] = None, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        logger.info(f"Fetching Outlook calendar events with connection_id: {connection_id}")
        try:
            result = await self.fetch_data(connection_id, "events", params, 'outlook')
            logger.info(f"Successfully fetched Outlook calendar events")
            return result
        except Exception as e:
            logger.error(f"Error fetching Outlook calendar events: {str(e)}")
            raise

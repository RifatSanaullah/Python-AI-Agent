import json
import logging
from typing import Dict, Any, Optional, List
from app.services.nango_service import NangoService

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("google_calendar_service")

class GoogleCalendarService(NangoService):
    def __init__(self):
        super().__init__()
        logger.info("GoogleCalendarService initialized")
    
    async def get_events(self, connection_id: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:

        logger.info(f"Fetching Google Calendar events with connection_id: {connection_id}")
        try:
            result = await self.fetch_data(connection_id, "google-calendar/events", params, 'google-calendar')
            logger.info(f"Successfully fetched Google Calendar events")
            return result
        except Exception as e:
            logger.error(f"Error fetching Google Calendar events: {str(e)}")
            raise

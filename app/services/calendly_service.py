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

   
    async def create_one_off_event_type(self, connection_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Creates a new one-off event type in Calendly.

        Args:
            connection_id: The Nango connection ID for Calendly.
            payload: A dictionary containing the parameters for creating the one-off event type.
                Expected structure:
                {
                    "name": "string",  # Required. Max 55 chars. E.g., "My Meeting"
                    "host": "string",  # Required. User URI. E.g., "https://api.calendly.com/users/AAAAAAAAAAAAAAAA"
                    "co_hosts": ["string"],  # Optional. List of co-host URIs. Max 9 items.
                    "duration": int,  # Required. Meeting duration in minutes. Max 720.
                    "timezone": "string",  # Optional. E.g., "America/New_York". Defaults to host's timezone.
                    "date_setting": {  # Required.
                        "type": "date_range",  # Required. Must be "date_range".
                        "start_date": "string",  # Required. Format: YYYY-MM-DD. E.g., "2020-01-07"
                        "end_date": "string"  # Required. Format: YYYY-MM-DD. E.g., "2020-01-08"
                    },
                    "location": {  # Required.
                        # Example for Custom Location:
                        "kind": "custom",  # Required for custom.
                        "location": "string" # Required for custom.
                        # Other location kinds (e.g., "google_conference", "zoom_conference")
                        # will have their own specific structures.
                    }
                }
        """
        logger.info(f"Creating Calendly one-off event type with connection_id: {connection_id}")
        try:
            result = await self.post_data(connection_id, "one_off_event_types", payload, 'calendly')
            logger.info(f"Successfully created Calendly one-off event type")
            return result
        except Exception as e:
            logger.error(f"Error creating Calendly one-off event type: {str(e)}")
            raise

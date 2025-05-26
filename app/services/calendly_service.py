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
        Creates a new one-off event type in Calendly by invoking a Nango action.
        The Nango action script is expected to transform this payload into the
        Calendly API format for the '/one_off_event_types' endpoint.

        Args:
            connection_id: The Nango connection ID for Calendly.
            payload: A dictionary containing the parameters for creating the one-off event type
                     (expected as 'fields' by the Nango script).
                Expected structure:
                {
                    "name": "string",                  // Event name/title
                    "description": "string",           // Event description
                    "duration": int,                   // Duration in minutes
                    "locationType": "string",          // E.g., "custom", "google_conference"
                    "location": "string",              // Location details (e.g., address or meeting link)
                    "startTime": "string",             // ISO 8601 date-time string
                    "endTime": "string",               // ISO 8601 date-time string
                    "inviteesCanChooseTime": bool      // If invitees can choose a time
                    // Potentially other fields like 'host_uri' if needed by the Nango script
                    // and not automatically handled by Nango/Calendly connection context.
                }
        """
        logger.info(f"Creating Calendly one-off event type via Nango action with connection_id: {connection_id}. Payload (fields for Nango script): {json.dumps(payload, indent=2)}")
        try:
            # "create-calendly-one-off-event" is an assumed Nango action ID for the script.
            # Adjust if your Nango action ID is different.
            result = await self.post_data(connection_id, "create-event", payload, 'calendly')
            logger.info(f"Successfully created Calendly one-off event type via Nango action. Response: {json.dumps(result, indent=2)}")
            return result
        except Exception as e:
            logger.error(f"Error creating Calendly one-off event type via Nango action: {str(e)}. Payload was: {json.dumps(payload, indent=2)}")
            raise

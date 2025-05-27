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
    
    async def get_events(self, connection_id: str, calendar_id: Optional[str] = None, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        logger.info(f"Fetching Outlook calendar events with connection_id: {connection_id}")
        try:
            result = await self.fetch_data(connection_id, "events", params, 'outlook')
            logger.info(f"Successfully fetched Outlook calendar events")
            return result
        except Exception as e:
            logger.error(f"Error fetching Outlook calendar events: {str(e)}")
            raise
    
    async def create_event(self, connection_id: str, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Create a calendar event in Outlook by invoking a Nango action.
        The Nango action script is expected to transform this payload into the
        Microsoft Graph API format.

        Args:
            connection_id: The Nango connection ID for Outlook authentication.
            payload: Dictionary containing event details (expected as 'fields' by the Nango script):
                - subject: (string) Event title.
                - description: (string) Event description (to be used for body.content).
                - startDateTime: (string) ISO 8601 date-time string for the event start.
                - endDateTime: (string) ISO 8601 date-time string for the event end.
                - timeZone: (string) The time zone for start and end times (e.g., "America/New_York").
                - attendees: (List[str]) A list of email addresses for attendees.
                (Other fields like 'location' can be added if the Nango script handles them)
                
        Returns:
            Dictionary containing the response from the Nango action, typically the created event details.
        """
        logger.info(f"Attempting to create Outlook calendar event via Nango action with connection_id: {connection_id}. Payload (fields for Nango script): {json.dumps(payload, indent=2)}")
        try:
            # "create-event" is assumed to be the Nango action ID that corresponds
            # to the provided Javascript snippet which calls the Graph API.
            result = await self.post_data(connection_id, "create-event", payload, 'outlook')
            logger.info(f"Outlook create_event (via Nango action) response: {json.dumps(result, indent=2)}")
            return result
        except Exception as e:
            logger.error(f"Error creating Outlook calendar event: {str(e)}. Payload was: {json.dumps(payload, indent=2)}")
            raise

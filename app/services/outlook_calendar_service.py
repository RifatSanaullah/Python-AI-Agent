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
    
    async def create_event(self, connection_id: str, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Create a calendar event in Outlook using Microsoft Graph API.
        
        Args:
            connection_id: The Nango connection ID for Outlook authentication
            payload: Dictionary containing event details including:
                - subject: Event title
                - body: Event description (contentType and content)
                - start: Start time (dateTime and timeZone)
                - end: End time (dateTime and timeZone)
                - location: Location details
                - attendees: List of attendees
                - isOnlineMeeting: Whether this is an online meeting (optional)
                - onlineMeetingProvider: Provider for online meeting (optional)
                
        Returns:
            Dictionary containing the created event details
        """
        logger.info(f"Attempting to create Outlook calendar event with connection_id: {connection_id}. Payload: {json.dumps(payload, indent=2)}")
        try:
            result = await self.post_data(connection_id, "create-event", payload, 'outlook')
            logger.info(f"Outlook create_event response: {json.dumps(result, indent=2)}")
            return result
        except Exception as e:
            logger.error(f"Error creating Outlook calendar event: {str(e)}. Payload was: {json.dumps(payload, indent=2)}")
            raise

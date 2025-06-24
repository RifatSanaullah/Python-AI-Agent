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

    async def create_event(self, connection_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Creates a new event in Google Calendar.
        Ref: https://developers.google.com/workspace/calendar/api/guides/create-events

        Args:
            connection_id: The Nango connection ID for Google Calendar.
            calendar_id: The ID of the calendar to create the event in.
                         Can be the calendar's email address or "primary".
        
        Example basic payload:
                {
                    "summary": "Team Meeting",
                    "description": "Discuss Q3 roadmap.",
                    "start": {
                        "dateTime": "2024-08-01T10:00:00-07:00",
                        "timeZone": "America/Los_Angeles"
                    },
                    "end": {
                        "dateTime": "2024-08-01T11:00:00-07:00",
                        "timeZone": "America/Los_Angeles"
                    },
                    "attendees": [
                        {"email": "user1@example.com"},
                        {"email": "user2@example.com"}
                    ],
                    "location": "Conference Room A",
                    "conferenceData": {
                        "createRequest": {
                            "requestId": "some-random-string-for-meet",
                            "conferenceSolutionKey": {"type": "hangoutsMeet"}
                        }
                    }
                }

        Returns:
            A dictionary containing the API response from Google Calendar.

        Raises:
            Exception: If there's an error during the API call.
        """
        logger.info(f"Attempting to create Google Calendar event in calendar '' with connection_id: {connection_id}. Payload: {json.dumps(payload, indent=2)}")
        try:
            # The endpoint for creating an event is /calendars/{calendarId}/events
            # This path is relative to the provider's base API URL proxied by Nango.
            endpoint = f"create-event" # Corrected endpoint
            result = await self.post_data(connection_id, endpoint, payload, 'google-calendar')
            logger.info(f"Google Calendar create_event response: {json.dumps(result, indent=2)}")
            return result
        except Exception as e:
            logger.error(f"Error creating Google Calendar event: {str(e)}. Payload was: {json.dumps(payload, indent=2)}")
            raise

    async def update_event(self, connection_id: str, event_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Updates an existing event in Google Calendar.
        """
        logger.info(f"Updating Google Calendar event {event_id} with connection_id: {connection_id}")
        try:
            # This action should be configured in Nango to PATCH /calendars/primary/events/{eventId}
            endpoint = "update-event"
            full_payload = {
                "eventId": event_id,
                "fields": payload
            }
            result = await self.post_data(connection_id, endpoint, full_payload, 'google-calendar')
            logger.info(f"Successfully updated Google Calendar event {event_id}")
            return result
        except Exception as e:
            logger.error(f"Error updating Google Calendar event {event_id}: {str(e)}")
            raise

    async def delete_event(self, connection_id: str, event_id: str) -> None:
        """
        Deletes an event from Google Calendar.
        """
        logger.info(f"Deleting Google Calendar event {event_id} with connection_id: {connection_id}")
        try:
            # This action should be configured in Nango to DELETE /calendars/primary/events/{eventId}
            endpoint = "delete-event"
            payload = {"eventId": event_id}
            await self.post_data(connection_id, endpoint, payload, 'google-calendar')
            logger.info(f"Successfully deleted Google Calendar event {event_id}")
        except Exception as e:
            logger.error(f"Error deleting Google Calendar event {event_id}: {str(e)}")
            raise

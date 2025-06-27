import requests
import logging
from app.config import settings
import app.services.cinc_service as cinc_service
from apscheduler.schedulers.background import BackgroundScheduler
import time
from datetime import datetime, timedelta
from app.services.call_handler import CallHandler
import asyncio

scheduler = BackgroundScheduler()
if not scheduler.running:
    scheduler.start()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

CINC_API_BASE_URL = "https://public.cincapi.com/v2"

async def register_cinc_webhook():
    """
    Register the webhook with CINC API.
    """
    webhook_url = f"https://wolf-ready-reliably.ngrok-free.app/new-cinc-lead"
    headers = {
        'Content-Type': 'application/json',
        'Authorization': 'eyJhbGciOiJSUzI1NiIsImtpZCI6IlJscDI4aFJHV0xoRkF5MyIsInR5cCI6IkpXVCJ9.eyJmaXJzdF9uYW1lIjoiTWFoaXIiLCJsYXN0X25hbWUiOiJNdXNsZWgiLCJlbWFpbCI6Im1haGlyLm11c2xlaEBib29tZXJzaHViLmNvbSIsInBob25lIjoiIiwiYXVkIjoicHVibGljIiwic2NvcGUiOiJhcGk6cmVhZCBhcGk6Y3JlYXRlIGFwaTp1cGRhdGUgYXBpOmV2ZW50IiwianRpIjoiZTYzMTNkMzAtZTZhYS00YTg1LThmM2MtNjVlOWZmYWY3OWJiIiwic3ViIjoiNzZkMjBkYWQtNmVhOC00ZTI3LWFlOTUtYmY0OGFlNmU2YWQxIiwidXNlcl90eXBlIjoiYWdlbnQiLCJsZWdhY3lfaWQiOiJNTTREMkQ1NTNCRTg4QTQzMzZBMUE4NUUzN0EzNkQzOEEwIiwidXNlcm5hbWUiOiJtYWhpci5tdXNsZWhAYm9vbWVyc2h1Yi5jb20iLCJyb2xlIjpbImNsaWVudCIsImJyb2tlciJdLCJpZHAiOiJpbnRlZ3JhdG9yIiwiY2xpZW50X25hbWUiOiJWZXJiYWNhbGwiLCJzaXRlIjoiRE4yM0VERTAzQ0IyMEE0OUNFOUE4Rjg1REIwQkZGOEQzQSIsImNsaWVudF9pZCI6IjA5ZDFkZjkwLTVkNDItNDhmOC05ZjM0LTVjYWY2Yzc2Njg3MyIsImFtciI6WyJwd2QiXSwibmJmIjoxNzUxMDQxNzgxLCJleHAiOjE3NTEwNDI2ODEsImlhdCI6MTc1MTA0MTc4MSwiaXNzIjoiaHR0cHM6Ly9hdXRodjIuY2luY2FwaS5jb20vaW50ZWdyYXRvciIsImxhc3RfbG9naW5fZGF0ZSI6MTc1MDk1NjE2MzAwN30.OxxvZrP7MTXVLpxl9IhQklyjd_kyt0R3LpJtvu6QZEEaOFeb307wKGqYT9JPEiJ-8MDGFPVFqUtHta4njzjY48EmQtDdxP8oZw-QBLcpFkgzums3Eh2r5ybuxoo17-Lm024LEMSJPF9jS_e_7aYbLYV5Va3o1Eifh1S9EerM3f6t7WPrgoKuMDg63VdSnRP0SZB8weTKNHDYYiN6bi7tuXtd-9XvZG-6cgHWO3xAV32o_Rtb2pxk8Qm0zXagNg0op5pUOgQIfK0365wnv0vq93_hCfH2DIcEg6WZlvL4EjWIK6k_YFaidhk7rbytFGd7bRAOBaSjy9U1HqYALO5zVQ'
    }
    data = {
        "url": webhook_url,
        "event_filters": [
            "lead.created"
        ]
    }

    try:
        response = requests.post(f"{CINC_API_BASE_URL}/site/webhook", headers=headers, json=data)
        response.raise_for_status()  # Raise an exception for bad status codes
        logger.info("Webhook registered successfully with CINC.")
        return response.json()
    except requests.exceptions.RequestException as e:
        error_content = None
        if e.response is not None:
            try:
                error_content = e.response.json()
            except Exception:
                error_content = e.response.text
        logger.error(f"Error registering webhook with CINC: {e}\nResponse: {error_content}")
        return {"error": str(e), "response": error_content}

async def fetch_and_print_lead_details(account_id: int, lead_id: str, connection_id: str = None):
    try:
        lead_details = await cinc_service.get_lead_details(account_id, lead_id, connection_id)
        # cell_phone = lead_details['info']['contact']['phone_numbers']['cell_phone']
        cell_phone = "+8801768082039"
        print(f"Cell phone: {cell_phone}")

        async def make_outbound_call():
            try:
                call_handler = CallHandler()
                call_sid = await call_handler.make_outgoing_call(cell_phone)
                logger.info(f"[CRON] Made outbound call to {cell_phone}, call_sid: {call_sid}")
            except Exception as e:
                logger.error(f"[CRON] Failed to make outbound call to {cell_phone}: {e}")

        def sync_make_outbound_call():
            asyncio.run(make_outbound_call())

        # Schedule the outbound call after 10 seconds
        run_date = datetime.now() + timedelta(seconds=5)
        scheduler.add_job(sync_make_outbound_call, 'date', run_date=run_date)

        return lead_details
    except Exception as e:
        print(f"Error fetching lead details for lead_id={lead_id}: {e}")
        return None

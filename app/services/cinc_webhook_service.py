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

        # Schedule the outbound call after the configured wait time
        run_date = datetime.now() + timedelta(minutes=settings.cinc_wait_min)
        scheduler.add_job(sync_make_outbound_call, 'date', run_date=run_date)

        return lead_details
    except Exception as e:
        print(f"Error fetching lead details for lead_id={lead_id}: {e}")
        return None

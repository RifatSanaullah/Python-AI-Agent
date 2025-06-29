import requests
import logging
from app.services.backend_service import BackendHandler
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


async def fetch_and_trigger_outbound(account_id: int, lead_id: str, connection_id: str = None):
    try:
        lead_details = await cinc_service.get_lead_details(account_id, lead_id, connection_id)
        cell_phone = lead_details['info']['contact']['phone_numbers']['cell_phone']
        print(f"lead_details: {lead_details}")
        
        async def make_outbound_call():
            try:
                # Check lead status after wait time - only call if still "New Lead"
                current_lead_details = await cinc_service.get_lead_details(account_id, lead_id, connection_id)
                current_stage = current_lead_details.get('pipeline', {}).get('stage', '')
                
                if current_stage != "New Lead":
                    print(f"[CRON] Lead {lead_id} is not in 'New Lead' stage (current: {current_stage}). Skipping outbound call.")
                    return
                
                print(f"[CRON] Lead {lead_id} is in 'New Lead' stage. Making outbound call.")
                
                update_data = {
                    "pipeline": {
                        "stage": "Attempted Contact",
                        "history": [
                            {
                                "stage": "Attempted Contact",
                                "staged_date": datetime.now().isoformat(),
                            }
                        ],
                    }
                }
                result = await cinc_service.update_lead(
                    account_id, 
                    lead_id, 
                    lead_data=update_data,
                    connection_id=connection_id
                )
                print(f"Lead updated: {result}")
                backend = BackendHandler()
                payload = {
                    "phone_number": cell_phone,
                    "account_id": account_id,
                }
                response = await backend.cinc_outbound_call(payload)
                print(f"[CRON] Outbound call triggered for {cell_phone}, response: {response}")
            except Exception as e:
                logger.error(f"[CRON] Failed to make outbound call to {cell_phone}: {e}")

        def sync_make_outbound_call():
            asyncio.run(make_outbound_call())

        # Schedule the outbound call after the configured wait time
        run_date = datetime.now() + timedelta(seconds=settings.cinc_wait_seconds)
        scheduler.add_job(sync_make_outbound_call, 'date', run_date=run_date)

        return lead_details
    except Exception as e:
        print(f"Error fetching lead details for lead_id={lead_id}: {e}")
        return None

import requests
import logging
from app.services.backend_service import BackendHandler
from app.config import settings
from app.services.cinc_service import CincService
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

# Create a CincService instance for this module
cinc_service = CincService()


async def fetch_and_trigger_outbound(account_id: int, lead_id: str, connection_id: str, update_details):
    try:
        # Get dynamic wait time from connection data first
        backend = BackendHandler()
        payload = {
            "phone_number": "temp",  # We just need this to get the wait time
            "account_id": account_id,
        }
        try:
            connection_data = await backend.get_connection_details(payload)
            print(f"[CRON] Full connection_data response: {connection_data}")
            wait_time_minutes = connection_data.get('outbound_cadence_interval', 5)
            print(f"[CRON] Extracted wait_time_minutes: {wait_time_minutes}")
            print(f"[CRON] Using dynamic wait time: {wait_time_minutes} minutes")
        except Exception as e:
            print(f"[CRON] Failed to get dynamic wait time, using default: 5 minutes")
            print(f"[CRON] Exception: {e}")
            wait_time_minutes = 5  # Default to 5 minutes if API call fails

        async def make_outbound_call():
            try:
                # Check lead status after wait time - only call if still "New Lead"
                current_lead_details = await cinc_service.get_lead_details(account_id, lead_id, connection_id)
                print(f"[CRON] Current lead details for lead {lead_id}: {current_lead_details}")
                
                # Extract the actual lead data from the response structure
                lead_data = current_lead_details
                if 'lead' in current_lead_details:
                    lead_data = current_lead_details['lead']
                
                current_stage = lead_data.get('pipeline', {}).get('stage', '')
                
                # Extract cell phone from the actual structure we received
                cell_phone = None
                try:
                    cell_phone = lead_data['info']['contact']['phone_numbers']['cell_phone']
                except (KeyError, TypeError):
                    logger.error(f"[CRON] Failed to extract cell phone from lead {lead_id}")
                    logger.error(f"[CRON] Lead data structure: {lead_data}")
                    return
                
                print("cell_phone", cell_phone)
                
                # Check if we have a valid phone number
                if not cell_phone or cell_phone.strip() == "":
                    logger.warning(f"[CRON] No valid cell phone found for lead {lead_id}. Skipping outbound call.")
                    return
                
                backend = BackendHandler()
                payload = {
                    "phone_number": cell_phone,
                    "account_id": account_id,
                }
                connection_data = await backend.get_connection_details(payload)
                print(connection_data, cell_phone)
                
                await update_details(account_id, lead_data, cell_phone, connection_data['agent_phone']['phone'])
                
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
                payload = {
                    "phone_number": cell_phone,
                    "account_id": account_id,
                }
                response = await backend.cinc_outbound_call(payload)
                print(f"[CRON] Outbound call triggered for {cell_phone}, response: {response}")
            except Exception as e:
                logger.error(f"[CRON] Failed to make outbound call for lead {lead_id}: {e}")

        def sync_make_outbound_call():
            asyncio.run(make_outbound_call())

        # Schedule the outbound call after the dynamic wait time
        run_date = datetime.now() + timedelta(minutes=wait_time_minutes)
        scheduler.add_job(sync_make_outbound_call, 'date', run_date=run_date)

        return True
    except Exception as e:
        print(f"Error fetching lead details for lead_id={lead_id}: {e}")
        return None

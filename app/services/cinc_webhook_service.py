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

cinc_service = CincService()


async def fetch_and_trigger_outbound(account_id: int, lead_id: str, connection_id: str, update_details, created_by_agent_id: str = None):
    try:
        # Get agent cell phone first
        if created_by_agent_id:
            try:
                agent_data = await cinc_service.get_agent(account_id, created_by_agent_id, connection_id)
                agent_cell_phone = agent_data.get('agent', agent_data)['info']['contact']['phone_numbers']['cell_phone']
                print(f"[CRON] Agent {created_by_agent_id} cell phone: {agent_cell_phone}")
            except Exception as e:
                print(f"[CRON] Failed to fetch agent data: {e}")
        
        # Get connection configuration using agent's phone
        backend = BackendHandler()
        payload = {"phone_number": "temp", "account_id": account_id, "agent_cell_number": agent_cell_phone}
        
        try:
            connection_data = await backend.get_connection_details(payload)
            wait_time_minutes = connection_data.get('outbound_cadence_interval', 5)
            is_cadence_enabled = connection_data.get('is_cadence_enabled', False)
            print(f"[CRON] Cadence enabled: {is_cadence_enabled}, Wait time: {wait_time_minutes} minutes")
        except Exception as e:
            print(f"[CRON] Failed to get connection data: {e}")
        
        # Only proceed with outbound if cadence is enabled
        if not is_cadence_enabled:
            print(f"[CRON] Cadence disabled for Agent. Skipping outbound call.")
            return False

        async def make_outbound_call():
            try:
                # Get current lead details
                current_lead_details = await cinc_service.get_lead_details(account_id, lead_id, connection_id)
                lead_data = current_lead_details.get('lead', current_lead_details)
                current_stage = lead_data.get('pipeline', {}).get('stage', '')
                
                # Extract lead cell phone
                cell_phone = lead_data['info']['contact']['phone_numbers']['cell_phone']
                if not cell_phone or cell_phone.strip() == "":
                    print(f"[CRON] No valid cell phone for lead {lead_id}. Skipping.")
                    return
                
                # Check if lead is still in "New Lead" stage
                if current_stage != "New Lead":
                    print(f"[CRON] Lead {lead_id} stage changed to '{current_stage}'. Skipping outbound.")
                    return
                
                print(f"[CRON] Making outbound call to {cell_phone} for lead {lead_id}")
                
                # Get connection data for the call
                payload = {"phone_number": cell_phone, "account_id": account_id, "agent_cell_number": agent_cell_phone}

                connection_data = await backend.get_connection_details(payload)
                
                # Update lead details and stage
                await update_details(account_id, lead_data, cell_phone, connection_data['agent_phone'])
                update_data = {
                    "pipeline": {
                        "stage": "Attempted Contact",
                        "history": [{
                            "stage": "Attempted Contact",
                            "staged_date": datetime.now().isoformat(),
                        }],
                    }
                }
                await cinc_service.update_lead(account_id, lead_id, update_data, connection_id)
                
                # Trigger outbound call
                response = await backend.cinc_outbound_call(payload)
                print(f"[CRON] Outbound call response: {response}")
                
            except Exception as e:
                logger.error(f"[CRON] Failed outbound call for lead {lead_id}: {e}")

        def sync_make_outbound_call():
            asyncio.run(make_outbound_call())

        # Schedule the outbound call
        run_date = datetime.now() + timedelta(minutes=wait_time_minutes)
        scheduler.add_job(sync_make_outbound_call, 'date', run_date=run_date)
        print(f"[CRON] Scheduled outbound call for lead {lead_id} at {run_date}")

        return True
    except Exception as e:
        print(f"[CRON] Error in fetch_and_trigger_outbound: {e}")
        return None

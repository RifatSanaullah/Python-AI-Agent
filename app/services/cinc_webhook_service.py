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

# Track scheduled jobs by phone number for cancellation
scheduled_jobs_by_phone = {}

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

CINC_API_BASE_URL = "https://public.cincapi.com/v2"

cinc_service = CincService()
def format_us_number_simple(number_str):
        digits = ''.join(filter(str.isdigit, number_str))
        if len(digits) == 10:
            return '+1' + digits
        elif len(digits) == 11 and digits.startswith('1'):
            return '+' + digits
        else:
            return number_str

async def fetch_and_trigger_outbound(account_id: int, lead_id: str, connection_id: str, update_details, created_by_agent_id: str = None):
    try:
        # Get agent cell phone first
        if created_by_agent_id:
            try:
                agent_data = await cinc_service.get_agent(account_id, created_by_agent_id, connection_id)
                agent_cell_phone = agent_data.get('agent', agent_data)['info']['contact']['phone_numbers']['cell_phone']
                agent_home_phone = agent_data.get('agent', agent_data)['info']['contact']['phone_numbers']['home_phone']
                print(f"[CRON] Agent {created_by_agent_id} cell phone: {agent_cell_phone}")
            except Exception as e:
                print(f"[CRON] Failed to fetch agent data: {e}")
        
        # Get connection configuration using agent's phone
        backend = BackendHandler()
        agent_cell_phone = format_us_number_simple(agent_cell_phone)
        payload = {"phone_number": "temp", "account_id": account_id, "agent_cell_number": agent_cell_phone}
        is_cadence_enabled = True
        wait_time_minutes = 5
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

        # Get lead phone number for tracking
        try:
            lead_details = await cinc_service.get_lead_details(account_id, lead_id, connection_id)
            lead_data = lead_details.get('lead', lead_details)
            lead_phone = lead_data['info']['contact']['phone_numbers']['cell_phone']
            
            # Clean phone number to consistent format for tracking
            clean_phone = ''.join(filter(str.isdigit, lead_phone))
            if len(clean_phone) == 11 and clean_phone.startswith('1'):
                clean_phone = clean_phone[1:]
            
        except Exception as e:
            print(f"[CRON] Failed to get lead phone for tracking: {e}")
            return False

        async def make_outbound_call():
            try:
                # Get current lead details
                current_lead_details = await cinc_service.get_lead_details(account_id, lead_id, connection_id)
                lead_data = current_lead_details.get('lead', current_lead_details)
                current_stage = lead_data.get('pipeline', {}).get('stage', '')
                lead_data['routing_phone'] = agent_home_phone
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
                
                # Remove from tracking after successful execution
                phone_key = f"{account_id}_{clean_phone}"
                if phone_key in scheduled_jobs_by_phone:
                    del scheduled_jobs_by_phone[phone_key]
                
            except Exception as e:
                logger.error(f"[CRON] Failed outbound call for lead {lead_id}: {e}")

        def sync_make_outbound_call():
            asyncio.run(make_outbound_call())

        # Schedule the outbound call
        run_date = datetime.now() + timedelta(minutes=wait_time_minutes)
        job = scheduler.add_job(sync_make_outbound_call, 'date', run_date=run_date)
        
        # Track job by phone number for potential cancellation
        phone_key = f"{account_id}_{clean_phone}"
        scheduled_jobs_by_phone[phone_key] = {
            'job': job,
            'lead_id': lead_id,
            'phone': clean_phone,
            'scheduled_at': run_date
        }
        
        print(f"[CRON] Scheduled outbound call for lead {lead_id} ({clean_phone}) at {run_date}")

        return True
    except Exception as e:
        print(f"[CRON] Error in fetch_and_trigger_outbound: {e}")
        return None


async def cancel_outbound_for_ai_response(account_id: int, phone_number: str):
    """Cancel scheduled outbound call when lead responds to AI"""
    try:
        # Clean phone number to match stored format
        clean_phone = ''.join(filter(str.isdigit, phone_number))
        if len(clean_phone) == 11 and clean_phone.startswith('1'):
            clean_phone = clean_phone[1:]
        
        phone_key = f"{account_id}_{clean_phone}"
        
        if phone_key in scheduled_jobs_by_phone:
            job_info = scheduled_jobs_by_phone[phone_key]
            job = job_info['job']
            lead_id = job_info['lead_id']
            
            try:
                # Cancel the scheduled job
                scheduler.remove_job(job.id)
                print(f"[AI_CANCEL] ✅ Canceled outbound call for lead {lead_id} ({clean_phone}) - AI response received")
                
                # Remove from tracking
                del scheduled_jobs_by_phone[phone_key]
                
            except Exception as e:
                print(f"[AI_CANCEL] ⚠️ Job {job.id} may have already been executed or removed: {e}")
                # Still remove from tracking even if job removal failed
                if phone_key in scheduled_jobs_by_phone:
                    del scheduled_jobs_by_phone[phone_key]
            
        else:
            print(f"[AI_CANCEL] ℹ️ No scheduled outbound call found for {clean_phone} (account {account_id})")
            
    except Exception as e:
        logger.error(f"[AI_CANCEL] Error canceling outbound for {phone_number}: {e}")

import base64
from sqlalchemy.orm import Session
# from app.services.playht_service import PlayHT
from app.services.twilio_service import TwilioService
from app.services.ai_service import AIService
# from app.services.ai_service_v2 import AIService
from app.services.s3_service import S3Service
from app.services.backend_service import BackendHandler
from app.services.polly_service import PollyService
from app.services.deepgram_service import DeepgramService
from app.services.assembly_ai_transcribe_service import TranscribeService
from app.services.elevenlabs_service import ElevenLabsService
from app.services.zoho_service import ZohoService
from app.services.hubspot_service import HubSpotService
from app.services.salesforce_service import SalesforceService
from app.services.calendly_service import CalendlyService
from app.services.google_calendar_service import GoogleCalendarService
from app.services.outlook_calendar_service import OutlookCalendarService
from websockets.exceptions import ConnectionClosedError, ConnectionClosedOK
import logging
from datetime import datetime_CAPI
from app.helpers.utils import get_interrupt_message, convert_mulaw_to_wav
from app.config import settings
from pydub import AudioSegment
from threading import Timer
import numpy as np

from io import BytesIO
import numpy as np
import soundfile as sf
import time , re
import traceback
from app.utils.responseformat import hubspot_patch_format
from app.utils.datetime_formatter import format_datetime_human_readable, format_datetime_range_human_readable, is_future_datetime
import json, asyncio
from app.services import cinc_service as cinc_service_module # Added CINC service module
from typing import Dict, Any # Ensure Dict and Any are imported for type hinting

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    # format='%(asctime)s.%(msecs)03d - %(levelname)s - %(message)s',
    # datefmt='%Y-%m-%d %H:%M:%S'
)
class CallHandler:
    def __init__(self):
        self.twilio_service = TwilioService()
        self.backend_service = BackendHandler()
        self.ai_service = AIService()
        self.s3_service = S3Service()
        # self.playht_service = PlayHT()
        self.elevenlabs_service = ElevenLabsService()
        self.zoho_service = ZohoService()
        self.hubspot_service = HubSpotService()
        self.salesforce_service = SalesforceService()
        self.calendly_service = CalendlyService()
        self.google_calendar_service = GoogleCalendarService()
        self.outlook_calendar_service = OutlookCalendarService()
        self.cinc_service = cinc_service_module # Initialize CINC Service
        # self.transcribe_service = TranscribeService(on_transcript=self.handle_transcript)
        self.sessions = {}
        self.agents = {}
        self.completed_sessions = {}
        self.timer = None
        self.loop= asyncio.get_running_loop()

    def get_business_agent(self, call_id: str):
        """Retrieve specific AI agent/business logic based on the dialed number."""
        return self.agents[call_id]
    
    async def is_silent_or_empty_mulaw_numpy(self, audio_data):
        try:
            # Decode Base64
            audio_stream = BytesIO(audio_data)

            # Read audio using soundfile
            audio, samplerate = sf.read(audio_stream, format="RAW", subtype="ULAW", channels=1, samplerate=8000)

            duration_seconds = len(audio) / samplerate
            # Check if empty
            if len(audio) == 0:
                return {"is_silent": True, "duration": 0.0}

            # Compute RMS (Root Mean Square) to detect silence
            rms = np.sqrt(np.mean(np.square(audio)))

            silence_threshold = 0.20  # Adjust as needed
            is_silent = rms < silence_threshold

            return {"is_silent": is_silent, "duration": duration_seconds}

        except Exception as e:
            print(f"Error processing audio: {e}")
            return True  # Assume silent if processing fails
        
    async def process_input(self, call_id, websocket):
        await websocket.accept()
        session = {
            "synthesis_service": None,
            "transcribe_service": None,
            "ai_interrupt": False,
            "ai_speaking": False,
            "wait_duration": 12,
            "prev_wait_duration": 0,
            "stream_sid": None,
            "background_sound": None,
            "end_call": False,
            "last_transcript_time" : None,
        }

        output_file = f"recordings/{call_id}.mulaw"
        # Open μ-law raw file for writing
        with open(output_file, 'wb') as mulaw_fp:
            pass  # Placeholder to ensure the file is created

        # with open(output_file, "ab") as f:
        try:
            while True:
                data = await websocket.receive_json()
                if data["event"] in ("connected", "start"):
                    print(f"Media WS: Received event '{data['event']}'")
                    continue
                if data['streamSid'] and not self.sessions[data['streamSid']]['websocket']:
                    self.sessions[data['streamSid']]['websocket'] = websocket
                    self.sessions[data['streamSid']]['agent'] = self.get_business_agent(call_id)
                    session = self.sessions[data['streamSid']]
                    # if self.agents[data['streamSid']['call_sid']]['STT']['name'] == 'Deepgram':
                    #     session['transcribe_service'].establish_dg_connection(self.agents[data['streamSid']['call_sid']]['STT']['model'])
                    # else: session['transcribe_service'].connect()

                if data['streamSid'] not in self.sessions or 'call_sid' not in self.sessions[data['streamSid']]:
                    continue

                # if (data['streamSid'] 
                # and self.sessions[data['streamSid']]['last_user_audio_time'] 
                # and time.time() - self.sessions[data['streamSid']]['last_user_audio_time'] > self.sessions[data['streamSid']]['wait_duration']):

                    # if data['streamSid'] and self.sessions[data['streamSid']]['wait_counter'] >= 2:
                    #     self.sessions[data['streamSid']]['wait_counter'] = 0
                    #     message = get_interrupt_message('end_call')
                    #     self.ai_service.add_message(data['streamSid'], "assistant", message)
                    #     await self.synthesize_response(message, data['streamSid'])
                    #     # Schedule the call to end after 2 seconds
                    #     self.clear_timer()
                    #     self.timer = Timer(5, self.twilio_service.hangup_call, args=[self.sessions[data['streamSid']]['call_sid']])
                    #     self.timer.start()
                    #     return
                    
                    # message = get_interrupt_message()
                    # self.ai_service.add_message(data['streamSid'], "assistant", message)
                    # await self.synthesize_response(message, data['streamSid'])
                    # self.sessions[data['streamSid']]['wait_counter'] += 1

                if data["event"] == "media":
                    media = data["media"]
                    chunk = media["payload"]
                    chunk_bytes = base64.b64decode(chunk)
                                            # Step 2: Check if the decoded data is empty
                                            # Convert byte data to an AudioSegment instance

                    result = await self.is_silent_or_empty_mulaw_numpy(chunk_bytes)
                    is_audio_silent = result['is_silent']

                    # is_audio_silent = await self.is_mulaw_stream_silent_base64(chunk_bytes)
                    # is_audio_silent = result['is_silent']

                    if not is_audio_silent:
                        # await self.on_user_speech(data['streamSid'])
                        self.sessions[data['streamSid']]['last_user_audio_time'] =  None
                        self.sessions[data['streamSid']]['wait_counter'] = 0

                    with open(output_file, "ab") as f:
                        f.write(chunk_bytes)
                    if (('route_call' not in self.agents[call_id] 
                        or self.agents[call_id]['route_call'] == False ) and
                        ( 'end_call' not in self.agents[call_id]
                        or self.agents[call_id]['end_call'] == False) ):
                        await self.twilio_service.enqueue_audio(data['streamSid'], chunk_bytes ,'audio_buffer')


                if data['streamSid'] and not self.twilio_service.is_empty(data['streamSid'], 'response_buffer'):
                    # print("Processing response buffers...")
                    response_audio = await self.twilio_service.get_or_dequeue_audio(data['streamSid'], 'response_buffer')
                    # await self.twilio_service.send_audio_stream(session['websocket'], data['streamSid'], response_audio)
                    # await self.twilio_service.send_control_command(session['websocket'], 'stop')
                    if self.sessions[data['streamSid']]['background_sound'] is True:
                        await self.stop_stream(data['streamSid'])
                    session['ai_speaking'] = True
                    with open(output_file, "ab") as f:
                        f.write(response_audio)

                if data['streamSid'] and not self.twilio_service.is_empty(data['streamSid'], 'audio_buffer'):
                    audio_data = await self.twilio_service.get_or_dequeue_audio(data['streamSid'], 'audio_buffer')
                    # await self.transcribe_service.transcribe(audio_data)
                    # await session['synthesis_service'].transcribe(audio_data)
                    await session['transcribe_service'].transcribe(audio_data)

        except ConnectionClosedError as e:
            print(f"Connection closed with error: {e.code} - {e.reason}")
        except ConnectionClosedOK as e:
            print(f"Connection closed normally: {e.code} - {e.reason}")
        except Exception as e:
            print("Unexpected error:", e)
        finally:
            print("WebSocket connection closed.")
            if self.agents[call_id]['STT']['name'] == 'Deepgram' and session['transcribe_service']:
                session['transcribe_service'].cancel_transmit()
            if session['stream_sid'] in self.ai_service.conversations:
                conversations = self.ai_service.conversations[session['stream_sid']]

                outputFile= f"recordings/{call_id}.wav"
                await convert_mulaw_to_wav(f"recordings/{call_id}.mulaw", outputFile)
                # os.remove(output_file)
                recordingUrl = await self.s3_service.uploadToS3(outputFile)
                agent_id = self.agents[call_id]['id']
                lead_id = None
                if 'lead_id' in self.agents[call_id] and self.agents[call_id]['lead_id'] is not None:
                    lead_id = self.agents[call_id]['lead_id']
                event_id = None
                if 'event_id' in self.agents[call_id] and self.agents[call_id]['event_id'] is not None:
                    event_id = self.agents[call_id]['event_id']
                previous_convo_summary = None
                if call_id in self.agents and 'previous_convo_summary' in self.agents[call_id]:
                    previous_convo_summary = self.agents[call_id]['previous_convo_summary']
                data = {
                    "call_sid" : call_id,
                    "conversations": conversations,
                    "recording_url" : recordingUrl,
                    "agent_id" : agent_id,
                    "lead_id" : lead_id,
                    "integrations" : self.agents[call_id]['integrations'],
                    "event_id" : event_id,
                    "previous_convo_summary" : previous_convo_summary,
                }

                try:
                    response = await self.backend_service.update_conversation_info(data)
                    isBoom = self.agents[call_id]['isBoom']
                    print("isBoom" , isBoom)
                    print({ "lead_id" : lead_id, "conversations": data['conversations']})
                    if isBoom is not None or isBoom == True or isBoom == 'true':
                        await self.backend_service.update_conversation_bh({ "lead_id" : lead_id, "conversations": data['conversations']})
                    else:
                        if 'summary' in response:
                            summary = response['summary']
                            await self.update_crm_data(call_id, data['lead_id'], data['integrations'], summary, response['appointment'], data['event_id'], data['previous_convo_summary'])
                except Exception as e:
                    print(f"Error updating conversation info: {str(e)}")
                    # Log the full exception traceback
                    import traceback
                    print(traceback.format_exc())

                self.ai_service.close_conversation(session['stream_sid'])
                self.twilio_service.remove_stream_from_queue(session['stream_sid'])
                del self.sessions[session['stream_sid']]
                self.agents[call_id]['websocket_closed'] = True
                # self.flush_agent(call_id)
                
            if self.agents[data['streamSid']['call_sid']]['TTS'] == 'Deepgram':
                await session['synthesis_service'].disconnect()
            if self.agents[data['streamSid']['call_sid']]['STT']['name'] == 'Deepgram':
                await session['transcribe_service'].disconnect()
            elif self.agents[data['streamSid']['call_sid']]['STT']['name'] == 'AssemblyAI':
                session['transcribe_service'].close()  # Close the transcriber service
            try:
                await websocket.close()
            except Exception as e:
                print("--Websocket connection Closed--")
    
    async def update_crm_data(self,call_id, lead_id: str, integrations, summary, appointment, prev_event_id, previous_convo_summary):
        # Log the integrations dictionary
        logging.info(f"Integrations for call {call_id}: {integrations}")
        event = appointment.get('eventData') if appointment else None
        
        # Get session info to extract account_id and connection_id for CINC
        session_info = self.get_business_agent(call_id)
        account_id = session_info.get("account_id") # This should be the account ID from the database
        cinc_connection_id = session_info.get("integrations", {}).get("cinc_connection_id") # Get CINC specific connection_id
        
        print(f"DEBUG - update_crm_data: account_id={account_id}, cinc_connection_id={cinc_connection_id}")
        print(f"DEBUG - update_crm_data: integrations={integrations}")

        # CINC Integration
        # Check if CINC is available by connection_id existence
        if cinc_connection_id and cinc_connection_id != "null" and cinc_connection_id != "" and account_id:
            try:
                # Prepare lead data for CINC update/create
                from datetime import datetime, timezone
                
                cinc_lead_data = {
                    "registered_date": datetime.now(timezone.utc).isoformat(),
                    "created_by": "AI_AGENT",
                    "info": {
                        "contact": {},
                        "source": "AI Call Assistant",
                        "status": "contacted" if lead_id else "unworked"
                    }
                }

                # Check if summary is already in CINC format (from Node.js backend)
                if summary.get("info") and summary["info"].get("contact"):
                    # Summary is already in CINC format, use it directly but merge with our defaults
                    cinc_lead_data.update(summary)
                    # Ensure required fields have defaults
                    if not cinc_lead_data.get("registered_date"):
                        cinc_lead_data["registered_date"] = datetime.now(timezone.utc).isoformat()
                    if not cinc_lead_data.get("created_by"):
                        cinc_lead_data["created_by"] = "AI_AGENT"
                    if not cinc_lead_data["info"].get("source"):
                        cinc_lead_data["info"]["source"] = "AI Call Assistant"
                    if not cinc_lead_data["info"].get("status"):
                        cinc_lead_data["info"]["status"] = "contacted" if lead_id else "unworked"
                    
                    # Fix phone number format for CINC (remove +1 prefix, keep just 10 digits)
                    contact = cinc_lead_data["info"]["contact"]
                    if contact.get("phone_numbers"):
                        phone_numbers = contact["phone_numbers"]
                        for phone_type in ["cell_phone", "home_phone"]:
                            if phone_numbers.get(phone_type):
                                phone = phone_numbers[phone_type]
                                # Convert +11433435421 to 1433435421 (10 digits)
                                digits = ''.join(filter(str.isdigit, phone))
                                if len(digits) == 11 and digits.startswith('1'):
                                    phone_numbers[phone_type] = digits[1:]  # Remove leading '1'
                                elif len(digits) == 10:
                                    phone_numbers[phone_type] = digits
                                # Remove empty phone numbers
                                if not phone_numbers[phone_type]:
                                    del phone_numbers[phone_type]
                else:
                    # Summary is in flat format, map to CINC format
                    contact = cinc_lead_data["info"]["contact"]
                    if summary.get("email"): 
                        contact["email"] = summary["email"]
                    if summary.get("first_name"): 
                        contact["first_name"] = summary["first_name"]
                    if summary.get("last_name"): 
                        contact["last_name"] = summary["last_name"]
                    
                    # Phone numbers - format for CINC (just 10 digits, no +1)
                    phone_numbers = {}
                    if summary.get("phone"): 
                        phone = summary["phone"]
                        digits = ''.join(filter(str.isdigit, phone))
                        if len(digits) == 11 and digits.startswith('1'):
                            phone_numbers["cell_phone"] = digits[1:]  # Remove leading '1'
                        elif len(digits) == 10:
                            phone_numbers["cell_phone"] = digits
                    if summary.get("home_phone"): 
                        phone = summary["home_phone"]
                        digits = ''.join(filter(str.isdigit, phone))
                        if len(digits) == 11 and digits.startswith('1'):
                            phone_numbers["home_phone"] = digits[1:]  # Remove leading '1'
                        elif len(digits) == 10:
                            phone_numbers["home_phone"] = digits
                    if phone_numbers: 
                        contact["phone_numbers"] = phone_numbers

                    # Map other CINC-specific fields from flat format
                    if summary.get("is_buyer") is not None: 
                        cinc_lead_data["info"]["is_buyer"] = summary["is_buyer"]
                    if summary.get("is_seller") is not None: 
                        cinc_lead_data["info"]["is_seller"] = summary["is_seller"]

                    # Buyer details - Always include buyer object with all expected fields
                    buyer = {}
                    buyer["average_price"] = summary.get("average_price", 0)
                    buyer["favorite_city"] = summary.get("favorite_city", "")
                    buyer["timeline"] = summary.get("timeline", "")
                    buyer["is_pre_qualified"] = summary.get("is_pre_qualified", False)
                    # Always add buyer object for CINC
                    cinc_lead_data["info"]["buyer"] = buyer

                    # Pipeline stage - Always include pipeline object
                    cinc_lead_data["pipeline"] = {
                        "stage": summary.get("pipeline_stage", "")
                    }

                # Handle notes (works for both CINC format and flat format)
                notes = []
                
                # Check if notes already exist in CINC format
                if cinc_lead_data.get("notes"):
                    # Filter out empty notes
                    notes.extend([note for note in cinc_lead_data["notes"] if note.get("content", "").strip()])
                
                # Add conversation summary as the main note if available
                if summary.get("description") and summary["description"].strip():
                    # Check if we already have a call summary note to avoid duplicates
                    has_call_summary = any(note.get("content", "").startswith("Call summary:") for note in notes)
                    if not has_call_summary:
                        notes.append({
                            "content": f"Call summary: {summary['description']}",
                            "category": "info",
                            "is_pinned": True,
                            "created_by": "AI_AGENT"
                        })
                
                # Add individual notes from the conversation if they exist in the summary
                if summary.get("notes") and isinstance(summary["notes"], list):
                    for note_item in summary["notes"]:
                        if isinstance(note_item, dict) and note_item.get("content", "").strip():
                            notes.append({
                                "content": note_item["content"],
                                "category": note_item.get("category", "info"),
                                "is_pinned": note_item.get("is_pinned", False),
                                "created_by": "AI_AGENT"
                            })
                
                # Add appointment note if exists
                if appointment and appointment.get("start_time") and appointment.get("end_time"):
                    appointment_time_str = format_datetime_range_human_readable(
                        appointment["start_time"], appointment["end_time"]
                    )
                    if appointment_time_str.strip():
                        notes.append({
                            "content": f"Appointment scheduled: {appointment_time_str}. Details: {appointment.get('summary', 'N/A')}",
                            "category": "appointment",
                            "is_pinned": True,
                            "created_by": "AI_AGENT"
                        })
                
                # Add a default conversation note if no other notes exist but we have basic info
                if not notes and (summary.get("first_name") or summary.get("email")):
                    contact_info = []
                    if summary.get("first_name"):
                        contact_info.append(f"Name: {summary.get('first_name', '')} {summary.get('last_name', '')}")
                    if summary.get("email"):
                        contact_info.append(f"Email: {summary['email']}")
                    if summary.get("phone"):
                        contact_info.append(f"Phone: {summary['phone']}")
                    
                    if contact_info:
                        notes.append({
                            "content": f"Contact captured via AI assistant. {', '.join(contact_info)}",
                            "category": "info",
                            "is_pinned": True,
                            "created_by": "AI_AGENT"
                        })
                
                # Only add notes if there are any
                if notes: 
                    cinc_lead_data["notes"] = notes
                
                # Remove empty/null fields that might cause issues with CINC API
                # For CINC, we need to be more careful about what we send
                def clean_for_cinc_update(obj):
                    """Clean data for CINC API - only include fields with actual values for updates"""
                    if isinstance(obj, dict):
                        cleaned = {}
                        for k, v in obj.items():
                            if v is None:
                                continue
                            elif isinstance(v, str) and v.strip() == "":
                                # For CINC updates, skip empty strings entirely
                                continue
                            elif isinstance(v, dict):
                                nested_cleaned = clean_for_cinc_update(v)
                                if nested_cleaned:  # Only add if the dict has content
                                    cleaned[k] = nested_cleaned
                            elif isinstance(v, list):
                                cleaned_list = [clean_for_cinc_update(item) for item in v if item is not None]
                                if cleaned_list:  # Only add if the list has content
                                    cleaned[k] = cleaned_list
                            else:
                                cleaned[k] = v
                        return cleaned
                    elif isinstance(obj, list):
                        return [clean_for_cinc_update(item) for item in obj if item is not None]
                    else:
                        return obj
                
                cinc_lead_data = clean_for_cinc_update(cinc_lead_data)

                # Debug: Print the final CINC lead data structure
                print(f"DEBUG - CINC lead data to be sent: {cinc_lead_data}")

                # Convert account_id to int as required by cinc_service
                int_account_id = int(account_id)

                if lead_id:
                    # For CINC updates, we should only send fields that actually changed
                    # This is more efficient and follows CINC best practices
                    update_data = {}
                    
                    # Only include fields that have meaningful values to update
                    if cinc_lead_data.get("info"):
                        info_updates = {}
                        info = cinc_lead_data["info"]
                        
                        # Contact updates (email, name, phone)
                        if info.get("contact"):
                            contact_updates = {}
                            contact = info["contact"]
                            if contact.get("email"):
                                contact_updates["email"] = contact["email"]
                            if contact.get("first_name"):
                                contact_updates["first_name"] = contact["first_name"]
                            if contact.get("last_name"):
                                contact_updates["last_name"] = contact["last_name"]
                            if contact.get("phone_numbers"):
                                contact_updates["phone_numbers"] = contact["phone_numbers"]
                            
                            if contact_updates:
                                info_updates["contact"] = contact_updates
                        
                        # Buyer updates (only if there are actual values)
                        if info.get("buyer"):
                            buyer_updates = {}
                            buyer = info["buyer"]
                            if buyer.get("average_price") and buyer["average_price"] > 0:
                                buyer_updates["average_price"] = buyer["average_price"]
                            if buyer.get("favorite_city") and buyer["favorite_city"].strip():
                                buyer_updates["favorite_city"] = buyer["favorite_city"]
                            if buyer.get("timeline") and buyer["timeline"].strip():
                                buyer_updates["timeline"] = buyer["timeline"]
                            if buyer.get("is_pre_qualified") is not None:
                                buyer_updates["is_pre_qualified"] = buyer["is_pre_qualified"]
                            
                            if buyer_updates:
                                info_updates["buyer"] = buyer_updates
                        
                        # Other info updates
                        if info.get("is_buyer") is not None:
                            info_updates["is_buyer"] = info["is_buyer"]
                        if info.get("is_seller") is not None:
                            info_updates["is_seller"] = info["is_seller"]
                        if info.get("status"):
                            info_updates["status"] = info["status"]
                        
                        if info_updates:
                            update_data["info"] = info_updates
                    
                    # Pipeline updates
                    if cinc_lead_data.get("pipeline") and cinc_lead_data["pipeline"].get("stage"):
                        update_data["pipeline"] = {"stage": cinc_lead_data["pipeline"]["stage"]}
                    
                    # Notes updates
                    if cinc_lead_data.get("notes") and len(cinc_lead_data["notes"]) > 0:
                        # Filter out empty notes and ensure proper CINC format
                        valid_notes = []
                        for note in cinc_lead_data["notes"]:
                            if note.get("content") and note["content"].strip():
                                # Ensure each note has the required CINC format
                                formatted_note = {
                                    "content": note["content"],
                                    "category": note.get("category", "info"),
                                    "created_by": note.get("created_by", "AI_AGENT")
                                }
                                # Add optional fields if they exist
                                if note.get("is_pinned") is not None:
                                    formatted_note["is_pinned"] = note["is_pinned"]
                                
                                valid_notes.append(formatted_note)
                        
                        if valid_notes:
                            update_data["notes"] = valid_notes
                    
                    # Only proceed with update if we have data to update
                    if update_data:
                        print(f"DEBUG - CINC update data (filtered): {update_data}")
                        await cinc_service_module.update_lead(
                            account_id=int_account_id, 
                            lead_id=lead_id, 
                            lead_data=update_data,
                            connection_id=cinc_connection_id
                        )
                        logging.info(f"CINC lead {lead_id} updated for account {account_id} via connection {cinc_connection_id}")
                    else:
                        print(f"DEBUG - No meaningful updates to send to CINC for lead {lead_id}")
                        logging.info(f"CINC lead {lead_id} - no updates needed for account {account_id}")
                else:
                    # Create new lead - check for email in nested structure
                    contact_info = cinc_lead_data.get("info", {}).get("contact", {})
                    has_email = contact_info.get("email")
                    
                    # If no email but have phone, create placeholder email
                    if not has_email:
                        phone_numbers = contact_info.get("phone_numbers", {})
                        cell_phone = phone_numbers.get("cell_phone")
                        if cell_phone:
                            # Create placeholder email from phone number
                            clean_phone = ''.join(filter(str.isdigit, cell_phone))
                            placeholder_email = f"lead_{clean_phone}@placeholder.com"
                            contact_info["email"] = placeholder_email
                            has_email = True
                            logging.info(f"Generated placeholder email for CINC lead: {placeholder_email}")
                    
                    if has_email:
                        created_lead = await cinc_service_module.create_lead(
                            account_id=int_account_id, 
                            lead_data=cinc_lead_data,
                            connection_id=cinc_connection_id
                        )
                        new_lead_id = created_lead.get("id")
                        if new_lead_id:
                            # Update session with new lead ID
                            if hasattr(self, 'agents') and call_id in self.agents:
                                self.agents[call_id]["cinc_lead_id"] = new_lead_id
                            # Update backend with new lead ID
                            await self.backend_service.update_call_info({
                                "call_id": call_id,
                                "cinc_lead_id": new_lead_id
                            })
                            logging.info(f"CINC lead created for account {account_id} via connection {cinc_connection_id}: {new_lead_id}")
                        else:
                            logging.warning(f"CINC lead creation for account {account_id} did not return an ID")
                    else:
                        logging.warning(f"Cannot create CINC lead for account {account_id} - missing email")

            except Exception as e:
                logging.error(f"CINC lead create/update failed for account {account_id} (conn: {cinc_connection_id}): {e}")
                import traceback
                logging.error(traceback.format_exc())


        if integrations and integrations["hubspot_connection_id"] is not None and integrations["hubspot_connection_id"] != '':
            summary["email"] = summary['email'].replace(" ", "")
            summary["phone"] = self.format_us_number_simple(summary["phone"])
            if summary['phone'] != self.agents[call_id]['from']:
                summary['mobilephone'] = self.format_us_number_simple(self.agents[call_id]['from'])
            notes  = summary['description']
            summary['description'] = ''
            if lead_id:
            # Update CRM Contact
            # summary = await self.chatgpt_service.get_summary(hubspot_patch_format, conversations)
                # summary["id"] = lead_id
                summary = self.remove_empty_values(summary)
                body = {
                    'Id' : lead_id,
                    'contact' : summary,
                    'note' : notes
                }
                await self.ai_service.hubspot_service.update_leads(integrations['hubspot_connection_id'], body)
            else:
                if summary['phone'] == '' :
                    summary['phone'] = self.format_us_number_simple(self.agents[call_id]['from'])
                summary = self.remove_empty_values(summary)
                body = {
                    'contact' : summary,
                    'note' : notes
                }
                await self.ai_service.hubspot_service.store_leads(integrations['hubspot_connection_id'], body)
                

        if integrations and integrations["salesforce_connection_id"] is not None and integrations["salesforce_connection_id"] != '':
            summary["Email"] = summary['Email'].replace(" ", "").replace(",",'')
            summary["Phone"] = self.formatToSalesforceNumber(summary["Phone"])
            if summary['Phone'] != self.agents[call_id]['from']:
                summary['MobilePhone'] = self.formatToSalesforceNumber(self.agents[call_id]['from'])
            # Update CRM Contact
            try:
                if lead_id:
            # summary = await self.chatgpt_service.get_summary(hubspot_patch_format, conversations)
                    # summary["Id"] = lead_id
                    if previous_convo_summary:
                        summary['Description'] = f"{previous_convo_summary}. Call Note on {datetime.now()}: {summary['Description']}"
                    if summary['LastName'] == '' :
                        summary['LastName'] = summary['FirstName']
                    if summary['Company'] == '':
                        summary['Company'] = 'N/A'
                    if summary['LastName'] != '':
                        summary = self.remove_empty_values(summary)
                        if summary['LastName'] == summary['FirstName']:
                            summary['FirstName'] = ''
                        body = {
                                'Id' : lead_id,
                                'lead' : summary
                            }
                        await self.ai_service.salesforce_service.update_leads(integrations['salesforce_connection_id'], body)
                else:
                    if summary['LastName'] == '' :
                        summary['LastName'] = summary['FirstName']
                    if summary['Company'] == '':
                        summary['Company'] = 'N/A'
                    if summary['LastName'] != '':
                        if summary['Phone'] == '' :
                            summary['Phone'] = self.formatToSalesforceNumber(self.agents[call_id]['from'])
                        summary = self.remove_empty_values(summary)
                        if summary['LastName'] == summary['FirstName']:
                            summary['FirstName'] = ''
                        await self.ai_service.salesforce_service.store_leads(integrations['salesforce_connection_id'], summary)
            except Exception as e:
                print("Lead Creat or Update failed" , e)

            try:
                if event is not None and event != '':
                    new_appointment = appointment['newAppointment']
                    update_appointment = appointment['updateAppointment']
                    delete_appointment = appointment['deleteAppointment']
                    if event['timezone']:
                        del event['timezone']
                    if prev_event_id is not None and prev_event_id != '':
                        if update_appointment:
                            body = {
                                'Id' : prev_event_id,
                                'event' : event
                            }
                            response = await self.ai_service.salesforce_service.update_event(integrations['salesforce_connection_id'], body)
                        elif delete_appointment:
                            response = await self.ai_service.salesforce_service.delete_event(integrations['salesforce_connection_id'], {"Id" : prev_event_id})
                    else:
                        response = await self.ai_service.salesforce_service.create_event(integrations['salesforce_connection_id'], event)
                        if response and 'id' in response and 'id' in appointment:
                            appointment_id = appointment['id']
                            await self.backend_service.update_appointment({"appointment_id" : appointment_id, "event_id" : response['id']})
 

            except Exception as e:
                print("Event Creation or update appointment Failed" , e)
        if integrations and integrations["zoho_connection_id"] is not None and integrations["zoho_connection_id"] != '':
            summary["Email"] = summary['Email'].replace(" ", "").replace(",",'')
            summary["Phone"] = self.format_us_number_simple(summary["Phone"])
            if summary['Phone'] != self.agents[call_id]['from']:
                summary['Mobile'] = self.format_us_number_simple(self.agents[call_id]['from'])
            # Update CRM Contact
            try:
                if lead_id:
            # summary = await self.chatgpt_service.get_summary(hubspot_patch_format, conversations)
                    # summary["Id"] = lead_id
                    if summary['Last_Name'] == '' :
                        summary['Last_Name'] = summary['First_Name']
                    if summary['Company'] == '':
                        summary['Company'] = 'N/A'
                    if summary['Last_Name'] != '':
                        summary = self.remove_empty_values(summary)
                        if summary['Last_Name'] == summary['First_Name']:
                            summary['First_Name'] = ''
                        body = {
                                'Id' : lead_id,
                                'lead' : summary,
                                'note' : {
                                    'Note_Title' : 'Call Summary',
                                    'Note_Content' : summary['Description']
                                } 
                        }
                        await self.ai_service.zoho_service.update_leads(integrations['zoho_connection_id'], body)
                else:
                    if summary['Last_Name'] == '' :
                        summary['Last_Name'] = summary['First_Name']
                    if summary['Company'] == '':
                        summary['Company'] = 'N/A'
                    if summary['Last_Name'] != '':
                        if summary['Phone'] == '' :
                            summary['Phone'] = self.format_us_number_simple(self.agents[call_id]['from'])
                        summary = self.remove_empty_values(summary)
                        if summary['Last_Name'] == summary['First_Name']:
                            summary['First_Name'] = ''
                        body = {
                                'lead' : summary,
                                'note' : {
                                    'Note_Title' : 'Call Summary',
                                    'Note_Content' : summary['Description'] 
                                } 
                        }
                        await self.ai_service.zoho_service.store_leads(integrations['zoho_connection_id'], body)
            except Exception as e:
                print("Lead Creat or Update failed" , e)



        # Google Calendar Event Handling
        if integrations and integrations.get("google_calendar_connection_id") and integrations["google_calendar_connection_id"] != '':
            try:
                if event is not None and event != '' and appointment.get('newAppointment'):
                    # The 'event' variable (derived from appointment['eventData']) is used as the payload.
                    # Its structure must align with Google Calendar API requirements
                    
                    # Transform the event data to Google Calendar API format
                    google_event_payload = {
                        "summary": event.get("Subject"),
                        "description": event.get("Description"),
                        "start": {
                            "dateTime": event.get("StartDateTime"),
                            "timeZone": event.get("timezone"),
                        },
                        "end": {
                            "dateTime": event.get("EndDateTime"),
                            "timeZone": event.get("timezone")  # Adjust time zone as needed      
                        }
                        # Attendees can be added her?e if available in 'event'
                        # "attendees": event.get("attendees", []) 
                    }
        
                    
                    response = await self.google_calendar_service.create_event(
                        integrations['google_calendar_connection_id'],
                        google_event_payload
                    )
                    if response and 'id' in response and 'id' in appointment:
                        appointment_id = appointment['id'] # BoomersHub internal appointment ID
                        await self.backend_service.update_appointment({
                            "appointment_id": appointment_id,
                            "google_calendar_event_id": response['id'] # Storing Google Calendar event ID
                        })
                        print(f"Successfully created Google Calendar event: {response['id']}")
                    elif response:
                        print(f"Google Calendar event creation response did not contain an ID: {response}")
                    else:
                        print("Google Calendar event creation returned no response.")
            except Exception as e:
                print(f"Google Calendar event creation failed: {str(e)}")
                import traceback
                print(traceback.format_exc())

        # Outlook Calendar Event Handling
        if integrations and integrations.get("outlook_connection_id") and integrations["outlook_connection_id"] != '':
            try:
                if event is not None and event != '' and appointment.get('newAppointment'):
                    # Prepare attendees list
                    outlook_attendees = []
                    contact_email_outlook = None
                    if summary and 'email' in summary and summary['email']: # HubSpot format
                        contact_email_outlook = summary['email']
                    elif summary and 'Email' in summary and summary['Email']: # Salesforce format
                        contact_email_outlook = summary['Email']
                    
                    if contact_email_outlook:
                        outlook_attendees.append(contact_email_outlook)
                    
                    # Transform event data to the format expected by the Nango script's 'fields'
                    outlook_event_payload = {
                        "subject": event.get("Subject"),
                        "description": event.get("Description"),
                        "startDateTime": event.get("StartDateTime"), # Expected as ISO 8601 string
                        "endDateTime": event.get("EndDateTime"),     # Expected as ISO 8601 string
                        "timeZone": event.get("timezone"), # Default if not in event
                        "attendees": outlook_attendees # List of email strings
                        # Add other fields like 'location' if your Nango script handles them
                    }
                    
                    # Basic validation for fields required by the Nango script
                    required_fields = ["subject", "startDateTime", "endDateTime", "timeZone"]
                    if not all(outlook_event_payload.get(k) for k in required_fields):
                        print(f"Outlook Calendar event payload (for Nango script) missing required fields: {outlook_event_payload}")
                    else:
                        response = await self.outlook_calendar_service.create_event(
                            integrations['outlook_connection_id'],
                            outlook_event_payload
                        )
                        if response and 'id' in response and 'id' in appointment:
                            appointment_id = appointment['id']
                            await self.backend_service.update_appointment({
                                "appointment_id": appointment_id,
                                "outlook_event_id": response['id']
                            })
                            print(f"Successfully created Outlook Calendar event: {response['id']}")
                        elif response:
                            print(f"Outlook Calendar event creation response did not contain an ID: {response}")
                        else:
                            print("Outlook Calendar event creation returned no response.")
            except Exception as e:
                print(f"Outlook Calendar event creation failed: {str(e)}")
                import traceback
                print(traceback.format_exc())

        # Calendly Scheduled Event Handling
        if integrations and integrations.get("calendly_connection_id") and integrations["calendly_connection_id"] != '':
            try:
                if event is not None and event != '' and appointment.get('newAppointment'):
                    # Transform event data to the format expected by the Nango script's 'fields'
                    # for creating a Calendly one-off event.
                    
                    # Assuming 'event' (from appointment['eventData']) contains the necessary details.
                    # The Nango script handles mapping these fields to the actual Calendly API structure.
                    calendly_event_payload = {
                        "name": event.get("Subject"), # Maps to Nango script's fields.name
                        "description": "30", # Maps to Nango script's fields.description
                        "duration": event.get("DurationInMinutes"), # Maps to Nango script's fields.duration
                        "locationType": event.get("LocationType", "Remote"), # Default to "custom" if not specified
                        "location": "Remote", # Maps to Nango script's fields.location
                        "startTime": event.get("StartDateTime"), # Maps to Nango script's fields.startTime
                        "endTime": event.get("EndDateTime"), # Maps to Nango script's fields.endTime
                        "inviteesCanChooseTime": event.get("InviteesCanChooseTime", False) # Default if not specified
                        # Ensure 'event' provides these keys or add defaults.
                        # 'host_uri' might be needed if not handled by Nango connection context.
                    }
                    
                    # Basic validation for fields required by the Nango script
                    required_calendly_fields = ["name", "duration", "locationType", "location", "startTime", "endTime"]
                    if not all(calendly_event_payload.get(k) is not None for k in required_calendly_fields): # Check for None explicitly for boolean field
                        print(f"Calendly one-off event payload (for Nango script) missing required fields: {calendly_event_payload}")
                    else:
                        response = await self.calendly_service.create_one_off_event_type(
                            integrations['calendly_connection_id'],
                            calendly_event_payload
                        )
                        # Calendly API for one-off event types might return the event URI or UUID.
                        # The Nango script returns response.data.resource, which should contain the URI/UUID.
                        event_resource_uri = None
                        if response and response.get('uri'): # Nango script returns response.data.resource which has a 'uri'
                            event_resource_uri = response.get('uri')
                        elif response and response.get('uuid'): # Fallback if 'uuid' is directly available
                            event_resource_uri = response.get('uuid')

                        if event_resource_uri and 'id' in appointment:
                            appointment_id = appointment['id']
                            await self.backend_service.update_appointment({
                                "appointment_id": appointment_id,
                                "calendly_event_uuid": event_resource_uri # Storing URI or UUID
                            })
                            print(f"Successfully created Calendly one-off event: {event_resource_uri}")
                        elif response:
                            print(f"Calendly one-off event creation response did not contain expected URI/UUID: {response}")
                        else:
                            print("Calendly one-off event creation returned no response.")
            except Exception as e:
                print(f"Calendly scheduled event creation failed: {str(e)}")
                import traceback
                print(traceback.format_exc())


    def remove_empty_values(self, data: dict) -> dict:
        """
        Removes keys with values that are None, empty strings, or "undefined" (as a string).
        """
        return {k: v for k, v in data.items() if v not in (None, "", "undefined")}
    
    def is_mulaw_stream_silent_base64(mulaw_bytes: bytes, silence_threshold: int = 500) -> bool:
        """
        Takes a base64-encoded µ-law audio chunk and returns True if it's silent.
        """
        # Convert µ-law to linear PCM (16-bit)
        pcm_data = audioop.ulaw2lin(mulaw_bytes, 2)

        # Convert to numpy array for analysis
        pcm_array = np.frombuffer(pcm_data, dtype=np.int16)

        # Measure maximum amplitude
        max_amplitude = np.max(np.abs(pcm_array)) if pcm_array.size > 0 else 0

        print(f"Max amplitude: {max_amplitude}")

        return max_amplitude < silence_threshold
                    
    def disable_ai_speaking(self, call_id):
            self.sessions[call_id]['ai_speaking'] = False
            self.sessions[call_id]['wait_duration'] = 12
            self.sessions[call_id]['ai_interrupt'] = False

    def initialize_transcriber(self, call_sid, call_id: str, Service : TranscribeService | DeepgramService):
        """Initialize transcriber with bound methods for handling transcripts and user speech."""
        return Service(
            on_transcript=self.create_on_transcript_handler(call_id),
            on_start=self.create_on_user_speech_handler(call_id),
            loop= self.loop,
            speak_model = self.agents[call_sid]['TTS']['voice']['model']
        )

    def create_on_transcript_handler(self, call_id: str):
        """Return a callback method for handling transcripts."""
        async def handler(transcript: str):
            await self.handle_transcript(transcript, call_id)
        return handler

    def create_on_user_speech_handler(self, call_id: str):
        """Return a callback method for handling user speech start."""
        async def handler():
            await self.on_user_speech(call_id)
        return handler 
               
    async def stop_stream(self,call_id):
        # await asyncio.sleep(1)  # Wait for 1 second
        self.sessions[call_id]['ai_interrupt'] =  True
        self.ai_service.update_interrupt_status(call_id, True)
        # self.sessions[call_id]['ai_speaking'] =  True
        # message = self.get_interrupt_message()
        await self.twilio_service.stop_audio_stream(self.sessions[call_id]['websocket'], call_id)
        # await self.synthesize_response(message, call_id)
        # if(self.timer):
        #     self.timer.cancel()
        #     self.timer = None
        # self.timer = Timer(self.sessions[call_id]['wait_duration'] - 1, self.disable_ai_speaking, args=[call_id])
        # self.timer.start()

        # await self.twilio_service.dequeue_all_except_next(call_id, 'response_buffer')
        self.sessions[call_id]['background_sound'] = False

    async def on_user_speech(self, call_id):
        if call_id in self.sessions and self.sessions[call_id]['ai_speaking'] == True:
            await self.stop_stream(call_id)
            self.sessions[call_id]['ai_speaking'] = False

    def contains_any_word(self, text:str):
        # Check if any word in the array exists in the text
        word_list = ['Bye','Goodbye','Have a nice day','Have a great day','Have a wonderful day']
        return any(word.lower() in text.lower() for word in word_list)
    
    async def handle_transcript(self, transcript, call_id):
        print(f"Transcript: {transcript}")
        # await self.enable_background_sound(call_id, True)
        if call_id not in self.sessions or 'call_sid' not in self.sessions[call_id]:
            return
        self.sessions[call_id]['ai_interrupt'] =  False
        self.ai_service.update_interrupt_status(call_id, False)
        streamingResponse = True
        if self.agents[self.sessions[call_id]['call_sid']]['TTS']['name'] == 'Elevenlabs':
            streamingResponse = False
        response = await self.ai_service.generate_response(call_id, transcript, self.synthesize_response, self.agents[self.sessions[call_id]['call_sid']]['aiClient'], self.sessions[call_id]['synthesis_service'].flush_sp_ws, streamingResponse)
        if 'End Call Message' in response or self.contains_any_word(transcript) or  self.contains_any_word(response):
            self.agents[self.sessions[call_id]['call_sid']]['end_call'] = True
            response = response.replace('End Call Message', '')
            # Schedule the call to end after 2 seconds
            # wait_time = self.sessions[call_id]['wait_duration']
            # if self.sessions[call_id]['last_transcript_time']:
            # wait_time = self.sessions[call_id]['wait_duration'] + self.sessions[call_id]['prev_wait_duration']
            wait_time = 15
            print("wait_time: ", wait_time)
            self.clear_timer()
            self.timer = Timer(wait_time, self.twilio_service.hangup_call, args=[self.sessions[call_id]['call_sid']])
            self.timer.start()
            
        if 'Routing Message' in response or 'I am forwarding the call' in response:
            response = response.replace('Routing Message', '')
            # Schedule the call to end after 2 seconds
            self.clear_timer()
            self.timer = Timer(13, self.twilio_service.redirect_call,
                          args=[
                            self.sessions[call_id]['call_sid'],
                            self.agents[self.sessions[call_id]['call_sid']]['routingInfo']['routingNumber'],
                            self.call_routed
                            ]
                        )
            self.timer.start()
        self.sessions[call_id]['last_transcript_time'] = None
        self.sessions[call_id]['prev_wait_duration'] = 0
        self.sessions[call_id]['wait_duration'] = 0
        print(f"Response: {response}")
        # await self.synthesize_response(response, call_id)

    def clear_timer(self):
        if(self.timer):
            self.timer.cancel()
            self.timer = None

    def call_routed(self, call_id):
        self.agents[call_id]['route_call'] = True

    async def get_agent_knowledge(self, call_id):
        data =  {        
            "knowledge" : self.agents[self.sessions[call_id]['call_sid']]['knowledge'],
            "aiInstructions" : self.agents[self.sessions[call_id]['call_sid']]['aiInstructions'],
            "agentName" : self.agents[self.sessions[call_id]['call_sid']]['name'],
            "gender" : self.agents[self.sessions[call_id]['call_sid']]['TTS']['voice']['gender'],
            "integrations" : self.agents[self.sessions[call_id]['call_sid']]['integrations'],
            "new_knowledge" : self.agents[self.sessions[call_id]['call_sid']]['new_knowledge'],
        }
        self.agents[self.sessions[call_id]['call_sid']]['knowledge'] = None
        self.agents[self.sessions[call_id]['call_sid']]['aiInstructions'] = None
        return data

    def chunk_text(self, text, chunk_size):
        chunks = []
        words = text.split()
        current_chunk = ''
        for word in words:
            if len(current_chunk) + len(word) <= chunk_size:
                current_chunk += ' ' + word
            else:
                chunks.append(current_chunk.strip())
                current_chunk = word
        if current_chunk:
            chunks.append(current_chunk.strip())
        return chunks
    
    async def synthesize_response(self, text: str, call_id):
        session = self.sessions.get(call_id)
        if not session or not text or text == '':
            return
        # start_time = datetime.now()
        model = self.agents[self.sessions[call_id]['call_sid']]['TTS']['voice']['model']
        # Select TTS provider based on environment variable
        if self.agents[self.sessions[call_id]['call_sid']]['TTS']['name'] == 'Deepgram':
            audio_stream = await session['synthesis_service'].stream_text_to_speech(text, call_id, self.queue_audio)
        # elif tts_provider == "playht":
        #     audio_stream = await self.playht_service.stream_text_to_speech(text, call_id, self.queue_audio)
        elif self.agents[self.sessions[call_id]['call_sid']]['TTS']['name'] == 'Elevenlabs':
            audio_stream = await self.sessions[call_id]["synthesis_service"].stream_text_to_speech(text, model, self.agents[self.sessions[call_id]['call_sid']]['TTS']['model'], call_id, self.queue_audio)
            # audio_stream = await self.sessions[call_id]["synthesis_service"].stream_text_to_speech(text, call_id, self.queue_audio)
            
            # await self.twilio_service.send_audio_stream(session['websocket'], call_id, audio_stream)
            # await self.twilio_service.enqueue_audio(call_id, audio_stream, 'response_buffer')
            # result = await self.is_silent_or_empty_mulaw_numpy(audio_stream)
            # session['prev_wait_duration'] = session['prev_wait_duration'] + session['wait_duration']
            # session['wait_duration'] = result['duration']

        else:
            raise ValueError(f"Unsupported TTS provider: {settings.tts_provider}")

        # end_time = datetime.now()
        # duration = (end_time - start_time).total_seconds() * 1000  # Calculate duration in milliseconds

        # result = await self.is_silent_or_empty_mulaw_numpy(audio_stream)
        # session['prev_wait_duration'] = session['prev_wait_duration'] + session['wait_duration']
        # session['wait_duration'] = result['duration']
        session['last_user_audio_time'] = time.time()
        return

        # print('audio streamed', session['last_user_audio_time'])

    async def queue_audio(self, call_id, audio_stream):
        session = self.sessions.get(call_id)
        if not session :
            return
        ai_interupted = session.get('ai_interrupt', False)
        if not ai_interupted and session['websocket'] is not None:
            
            await self.twilio_service.send_audio_stream(session['websocket'], call_id, audio_stream)
            await self.twilio_service.enqueue_audio(call_id, audio_stream ,'response_buffer')
            result = await self.is_silent_or_empty_mulaw_numpy(audio_stream)
            session['prev_wait_duration'] = session['prev_wait_duration'] + session['wait_duration']
            session['wait_duration'] = result['duration']
        # else:
        #     self.sessions[call_id]['ai_interrupt'] = False

    def initialize_session_info(self, stream_sid, call_sid):
        # Initialize a session for this specific call
        
        self.sessions[stream_sid] = {
                "ai_speaking": False,
                "ai_interrupt": False,
                "wait_counter": 0,
                "wait_duration": 12,
                "prev_wait_duration": 0,
                "stream_sid": stream_sid,
                "background_sound": None,
                "websocket" : None,
                "call_sid" : call_sid,
                "last_user_audio_time" : None
            }
        if self.agents[call_sid]['STT']['name'] == 'Deepgram':
            self.sessions[stream_sid]["transcribe_service"] = self.initialize_transcriber(call_sid, stream_sid, DeepgramService)
            # self.sessions[stream_sid]["synthesis_service"] = self.sessions[stream_sid]["transcribe_service"]
        elif self.agents[call_sid]['STT']['name'] == 'AssemblyAI':
            self.sessions[stream_sid]["transcribe_service"] = self.initialize_transcriber(call_sid, stream_sid, TranscribeService)
            # self.sessions[stream_sid]["synthesis_service"] = self.initialize_transcriber(stream_sid, DeepgramService)
        else :
            self.sessions[stream_sid]["transcribe_service"] = self.initialize_transcriber(call_sid, stream_sid, DeepgramService)
            # self.sessions[stream_sid]["synthesis_service"] = self.sessions[stream_sid]["transcribe_service"]
        


        if self.agents[call_sid]['TTS']['name'] == 'Deepgram':
            if self.agents[call_sid]['STT']['name'] == 'Deepgram':
                self.sessions[stream_sid]["synthesis_service"] = self.sessions[stream_sid]["transcribe_service"]
            else :
                self.sessions[stream_sid]["synthesis_service"] = self.initialize_transcriber(call_sid, stream_sid, DeepgramService)
        elif self.agents[call_sid]['TTS']['name'] == 'Elevenlabs':
            self.sessions[stream_sid]["synthesis_service"] = self.elevenlabs_service
        else:
            self.sessions[stream_sid]["synthesis_service"] = self.initialize_transcriber(call_sid, stream_sid, DeepgramService)

        # if stream_sid not in self.sessions:
        #     self.sessions[stream_sid]={
        #         "ai_speaking": False,
        #         "ai_interrupt": False,
        #         "wait_counter": 0,
        #         "wait_duration": 12,
        #         "prev_wait_duration": 0,
        #         "stream_sid": stream_sid,
        #         "background_sound": None,
        #         "websocket" : None,
        #         "call_sid" : call_sid,
        #         "last_user_audio_time" : None
        #     }

    def formatToSalesforceNumber(self, phone):
        digits = re.sub(r'\D', '', phone)
        if len(digits) == 10:
            return f'1 ({digits[0:3]}) {digits[3:6]}-{digits[6:]}'
        elif len(digits) == 11 and digits.startswith('1'):
            return f'1 ({digits[1:4]}) {digits[4:7]}-{digits[7:]}'
        else:
            return phone 
        
    def format_us_number_simple(self, number_str):
        digits = ''.join(filter(str.isdigit, number_str))
        if len(digits) == 10:
            return '+1' + digits
        elif len(digits) == 11 and digits.startswith('1'):
            return '+' + digits
        else:
            return number_str
        
    def format_us_phone(self, number: str):
        number = self.format_us_number_simple(number)
        if number.startswith("+1") and len(number) == 12:
            area_code = number[2:5]
            first_part = number[5:8]
            second_part = number[8:]
            return f"({area_code}) {first_part}-{second_part}"
        else:
            return number
        
    async def handle_call(self, call_id: str, data):
        print("Handling call...")
        api_response = await self.backend_service.create_call_info(data)
        self.agents[call_id] = api_response['data']['agent']
        self.agents[call_id]['isBoom'] = data['isBoom']
        self.agents[call_id]['complete_call'] = False
        self.agents[call_id]['websocket_closed'] = False
        self.agents[call_id]['end_call'] = False
        self.agents[call_id]['route_call'] = False
        self.agents[call_id]['from'] = data['from']
        self.agents[call_id]['previous_convo_summary'] = None
        self.agents[call_id]['new_knowledge'] = False
        self.agents[call_id]['aiClient'] = api_response['data']['aiClient']
        self.agents[call_id]['STT'] = api_response['data']['STT']
        self.agents[call_id]['TTS'] = api_response['data']['TTS']


        
        # Add user preference for allowing meeting conflicts
        if 'userPreference' in api_response['data'] and 'allowMeetingConflict' in api_response['data']['userPreference']:
            self.agents[call_id]['allowMeetingConflict'] = api_response['data']['userPreference']['allowMeetingConflict']
        else:
            self.agents[call_id]['allowMeetingConflict'] = False  # Default to False if not specified

        if 'appointment' in api_response['data'] and 'eventId' in api_response['data']['appointment']:
            self.agents[call_id]['event_id'] = api_response['data']['appointment']['eventId']

        self.agents[call_id]['integrations'] = {
                "hubspot_connection_id": None,
                "zoho_connection_id": None,
                "salesforce_connection_id": None,
                "calendly_connection_id": None,
                "google_calendar_connection_id": None,
                "cinc_connection_id": None,
        }
        self.agents[call_id]['lead_id'] = None
        if 'integrations' in api_response['data']:
            self.agents[call_id]['integrations'] = api_response['data']['integrations']
            print(f"DEBUG - Integrations received from backend: {api_response['data']['integrations']}")
        else:
            print("DEBUG - No integrations found in backend response")
        
        # Also add user_id to agent data for CINC integration
        if 'user' in api_response['data'] and 'id' in api_response['data']['user']:
            self.agents[call_id]['user_id'] = api_response['data']['user']['id']
        elif 'userId' in api_response['data']:
            self.agents[call_id]['user_id'] = api_response['data']['userId']
        elif 'user_id' in api_response['data']:
            self.agents[call_id]['user_id'] = api_response['data']['user_id']
        elif 'agent' in api_response['data'] and 'user_id' in api_response['data']['agent']:
            self.agents[call_id]['user_id'] = api_response['data']['agent']['user_id']
        elif 'agent' in api_response['data'] and 'userId' in api_response['data']['agent']:
            self.agents[call_id]['user_id'] = api_response['data']['agent']['userId']
        else:
            self.agents[call_id]['user_id'] = None
        
        print(f"DEBUG - Final agent integrations: {self.agents[call_id]['integrations']}")
        print(f"DEBUG - Agent user_id: {self.agents[call_id].get('user_id')}")
        print(f"DEBUG - Agent keys: {list(self.agents[call_id].keys())}")

        
        response = self.twilio_service.initialize_call(call_id)
        # self.transcribe_service.connect()  # Connect the transcriber service
        # await self.initialize_session_info(call_id)

        return response

    async def make_outgoing_call(self, phone_number: str):
        call_sid = self.twilio_service.make_call(phone_number)
        return call_sid

    async def handle_stream_callback(self, data):
        """Handle the stream callback to get the streamSid."""
        stream_sid = data.get("StreamSid")
        call_sid = data.get("CallSid")
        print(f"Stream SID: {stream_sid}, Call SID: {call_sid}")
        self.initialize_session_info(stream_sid, call_sid)
        print("stt: ",self.agents[call_sid]['STT']['name'])
        if self.agents[call_sid]['STT']['name'] == 'Deepgram':
            await self.sessions[stream_sid]['transcribe_service'].establish_dg_connection(self.agents[call_sid]['STT']['model'])
        else: self.sessions[stream_sid]['transcribe_service'].connect()
        print("tts: ",self.agents[call_sid]['TTS']['name'])
        
        # if self.agents[call_sid]['TTS']['name'] == 'Elevenlabs':
        #     await self.sessions[stream_sid]['synthesis_service'].establish_connection( self.agents[call_sid]['TTS']['voice']['model'], self.agents[call_sid]['TTS']['model'])
        if self.agents[call_sid]['TTS']['name'] == 'Deepgram':
            await self.sessions[stream_sid]['transcribe_service'].establish_sp_connection(self.agents[call_sid]['TTS']['voice']['model'])
        # self.sessions[call_sid]['stream_sid'] = stream_sid
        print("Done initializing session info")

        updaedata= {
            "stream_sid" : stream_sid,
            "call_sid" : call_sid
        }
        await self.backend_service.update_call_info(updaedata)
        if (self.agents[call_sid]['isAvailable'] == False):
            await self.synthesize_response('Currenty we are not available, Please contact us in our available time', stream_sid)
            # Schedule the call to end after 2 seconds
            self.clear_timer()
            self.timer = Timer(5, self.twilio_service.hangup_call, args=[call_sid])
            self.timer.start()
            return
        greetings = self.agents[call_sid]['greetings']
        result = await self.gather_contact_info(call_sid, greetings)
        fullname = result['fullname']
        greetings = result['greetings']
        email = result['email']
        phone = result['phone']
        description = result['description']
        existing_appointment = result['existing_appointment']
        print("Existing appointment: ", existing_appointment)
        isAllowMeetingConflict = self.agents[call_sid]['allowMeetingConflict']
        print("isAllowMeetingConflict: ", isAllowMeetingConflict)

        await self.synthesize_response(greetings , stream_sid)

        if self.agents[call_sid]['STT']['name'] == 'Deepgram':
            await self.sessions[stream_sid]['transcribe_service'].flush_sp_ws()

        await self.ai_service.process_initial_message(stream_sid, self.get_agent_knowledge)
        self.ai_service.add_message(stream_sid, "assistant", greetings)
        self.ai_service.add_system_message(stream_sid, "assistant", greetings)
        
        if fullname is not None and fullname != "":
            self.ai_service.add_message(stream_sid, "user", f"My Name is: {fullname}")
            self.ai_service.add_system_message(stream_sid, "system", f"Don't forget. This is the Name of the user you will use in this conversation: {fullname}")
        if email is not None and email != "":
            self.ai_service.add_message(stream_sid, "user", f"My Email Address is: {email}")
            self.ai_service.add_system_message(stream_sid, "system", f"Don't forget. This is the email address of the user you will use in this conversation : {email}.")
        if phone is not None and phone != "":
            self.ai_service.add_message(stream_sid, "user", f"My Phone Number is: {phone}")
            self.ai_service.add_system_message(stream_sid, "system", f"Don't forget. This is the Phone Number of the user you will use in this conversation: {phone}")
        else:
            self.ai_service.add_system_message(stream_sid, "system", f"This is the Phone Number of the user you will use in this conversation and you can ask the user if he/she wants to change the phone number: {self.format_us_phone(self.agents[call_sid]['from'])}")
        if description is not None and description != "":
            self.ai_service.add_system_message(stream_sid, "system", f"In Previous conversations with you this was the summary and you can use this info in this phone call: {description}")
       
        if not isAllowMeetingConflict and existing_appointment is not None and existing_appointment != "":
            print("Existing appointment found: ", existing_appointment)
            self.ai_service.add_system_message(
            stream_sid,
            "system",
            f"""Task: if user wants to schedule an appointment or meeting.

            Specifics:
            1. The booked time slots are: {existing_appointment}
            2. If the existing_appointment variable indicates the slot is booked, inform the user it's unavailable and ask them to choose another time or date
            """
        )


        return "OK", 200
    
    def modify_greeting(self, name, greetings, call_sid):
        greetings = greetings.replace('Hello', '')
        if call_sid in self.agents and "id" in self.agents[call_sid]:
            agent_id = self.agents[call_sid]['id']
            if agent_id == '17' or agent_id == 17:
                greetings = f'Hi {name}, welcome back! This is Cindy — happy to assist you again with your senior living needs. How can I help you today?'
                return greetings
            elif agent_id == '16' or agent_id == 16:
                greetings = f'Hi {name}, welcome back! This is Sam — happy to assist you again with your real estate needs. How can I help you today?'
                return greetings
        greetings= 'Hello ' + name + ', ' + greetings
        return greetings
    
    async def gather_contact_info(self, call_sid, greetings):
        fullname = None
        email = None
        phoneNumber = None
        description = None
        existing_appointment = None
        crmUserId = None
        isBoom = self.agents[call_sid]['isBoom']

        if isBoom is not None or isBoom == True or isBoom == 'true':
            result = await self.backend_service.get_lead_info_boom({"phone" : self.agents[call_sid]['from'] })
            if result and 'data' in result and result['data'] is not None:
                details = result['data']
                fullname = details['firstName']
                email = details['email']
                phoneNumber = details['phone']
                description = details['notes']
                crmUserId = details['id']
                greetings = self.modify_greeting(fullname, greetings,call_sid)
                self.agents[call_sid]['new_knowledge'] = True
        elif self.agents[call_sid]['integrations']['salesforce_connection_id']:

            formatted_number = self.formatToSalesforceNumber(self.agents[call_sid]['from'])
            result = await self.ai_service.salesforce_service.get_lead_by_phone(self.agents[call_sid]['integrations']['salesforce_connection_id'], formatted_number)
            
            if len(result) > 0:
                details = result[0]
                fullname = details['LastName']
                # if details['FirstName']:
                #     fullname = details['FirstName'] + ' ' + details['LastName']
                crmUserId = details['Id']
                email = details['Email']
                phoneNumber = details['Phone']
                description = details['Description']
                greetings = self.modify_greeting(fullname, greetings, call_sid)
                self.agents[call_sid]['new_knowledge'] = True

        elif self.agents[call_sid]['integrations']['hubspot_connection_id']:

            result = await self.ai_service.hubspot_service.get_contact_by_phone(self.agents[call_sid]['integrations']['hubspot_connection_id'], self.agents[call_sid]['from'])
            
            if 'results' in result and len(result['results']) > 0:
                details = result['results'][0]['properties']
                fullname = details['firstname'] + ' ' + details['lastname']
                email = details['email']
                phoneNumber = details['phone']
                description = details['notes']
                crmUserId = result['results'][0]['id']
                greetings = self.modify_greeting(fullname, greetings, call_sid)
                self.agents[call_sid]['new_knowledge'] = True

        elif self.agents[call_sid]['integrations']['zoho_connection_id']:

            result = await self.ai_service.zoho_service.get_lead_by_phone(self.agents[call_sid]['integrations']['zoho_connection_id'], self.agents[call_sid]['from'])
            
            if len(result) > 0:
                details = result[0]
                fullname = details['Last_Name']
                if details['First_Name'] and details['First_Name'] is not None:
                    fullname = details['First_Name']
                crmUserId = details['Id']
                email = details['Email']
                phoneNumber = details['Phone']
                description = details['Description']
                greetings = self.modify_greeting(fullname, greetings, call_sid)
                self.agents[call_sid]['new_knowledge'] = True

        elif self.agents[call_sid]['integrations']['cinc_connection_id']:
            try:
                # Get account_id from agent info
                account_id = self.agents[call_sid].get('account_id')
                if account_id:
                    result = await self.cinc_service.get_leads_by_phone(
                        account_id=account_id, 
                        phone=self.agents[call_sid]['from'],
                        connection_id=self.agents[call_sid]['integrations']['cinc_connection_id']
                    )
                    
                    if result and len(result) > 0:
                        # Use the first matching lead
                        lead = result[0]
                        contact_info = lead.get('info', {}).get('contact', {})
                        
                        # Extract contact information
                        first_name = contact_info.get('first_name', '')
                        last_name = contact_info.get('last_name', '')
                        
                        if first_name and last_name:
                            fullname = f"{first_name} {last_name}"
                        elif first_name:
                            fullname = first_name
                        elif last_name:
                            fullname = last_name
                        
                        email = contact_info.get('email')
                        
                        # Get phone number from the lead
                        phone_numbers = contact_info.get('phone_numbers', {})
                        if phone_numbers.get('cell_phone'):
                            phoneNumber = phone_numbers['cell_phone']
                        elif phone_numbers.get('home_phone'):
                            phoneNumber = phone_numbers['home_phone']
                        
                        # Extract description from notes if available
                        notes = lead.get('notes', [])
                        if notes:
                            # Combine all note contents
                            description = '; '.join([note.get('content', '') for note in notes if note.get('content')])
                        
                        # Set CINC lead ID for future updates
                        crmUserId = lead.get('id')
                        if crmUserId:
                            self.agents[call_sid]['cinc_lead_id'] = crmUserId
                        
                        greetings = self.modify_greeting(fullname, greetings, call_sid)
                        self.agents[call_sid]['new_knowledge'] = True
                        
                        print(f"DEBUG - Found CINC lead: {fullname}, Email: {email}, Phone: {phoneNumber}")
                        
            except Exception as e:
                print(f"Error fetching CINC lead by phone {self.agents[call_sid]['from']}: {e}")


        if self.agents[call_sid]['integrations'].get('calendly_connection_id'):
            # Check if there are any scheduled events for this user in Calendly
            print(f"Calendly connection ID: {self.agents[call_sid]['integrations']['calendly_connection_id']}")

            try:
                # First get the user information
                user_result = await self.calendly_service.get_user(
                    self.agents[call_sid]['integrations']['calendly_connection_id']
                )
                
                # Extract user info from response format
                user_info = None
                if user_result and 'records' in user_result and len(user_result['records']) > 0:
                    user_info = user_result['records'][0]
                    # Add user name from Calendly if available
                    if not fullname and user_info:
                        if 'firstName' in user_info and 'lastName' in user_info:
                            fullname = f"{user_info['firstName']} {user_info['lastName']}".strip()
                        elif 'firstName' in user_info:
                            fullname = user_info['firstName']
                        elif 'lastName' in user_info:
                            fullname = user_info['lastName']
                    
                    if not email and 'email' in user_info:
                        email = user_info['email']
                    
                    # Now check for scheduled events
                    try:
                        events_result = await self.calendly_service.get_events(
                            self.agents[call_sid]['integrations']['calendly_connection_id']
                        )
                        
                        # Extract events from response format
                        events_collection = []
                        if events_result and 'records' in events_result:
                            events_collection = events_result['records']
                        elif events_result and 'collection' in events_result:
                            events_collection = events_result['collection']
                        
                        if events_collection and len(events_collection) > 0:
                            # Set existing_appointment with formatted times
                            appointment_times = []
                            for event in events_collection:
                                if 'start_time' in event:
                                    # Only include future appointments
                                    if is_future_datetime(event['start_time']):
                                        # Check if end_time is available in Calendly event
                                        end_time = event.get('end_time', None)
                                        formatted_time = format_datetime_range_human_readable(event['start_time'], end_time)
                                        appointment_times.append(formatted_time)
                            
                            if appointment_times:
                                if existing_appointment:
                                    existing_appointment += ", " + ", ".join(appointment_times)
                                else:
                                    existing_appointment = ", ".join(appointment_times)
                            
                            # We have scheduled events, update description with this info
                            events_count = len(events_collection)
                            calendly_info = f"Has {events_count} upcoming Calendly appointment"
                            calendly_info += "s" if events_count > 1 else ""
                            
                            if description:
                                description += f" {calendly_info}."
                            else:
                                description = calendly_info + "."
                        else:
                            print("No upcoming Calendly events found.")
                    except Exception as events_error:
                        print(f"Error fetching Calendly events: {str(events_error)}")
                        import traceback
                        print(traceback.format_exc())
                        
            except Exception as e:
                print(f"Error checking Calendly events: {str(e)}")
                import traceback
                print(traceback.format_exc())
                
        if self.agents[call_sid]['integrations'].get('google_calendar_connection_id'):
            # Check if there are any scheduled events for this user in Google Calendar
            print(f"Google Calendar connection ID: {self.agents[call_sid]['integrations']['google_calendar_connection_id']}")

            try:
                # Get calendar events
                events_result = await self.google_calendar_service.get_events(
                    self.agents[call_sid]['integrations']['google_calendar_connection_id']
                )
                
                # print("=== GOOGLE CALENDAR EVENTS ===",json.dumps(events_result, indent=2))
                # Extract events from response format
                events_collection = []
                if events_result and 'records' in events_result:
                    events_collection = events_result['records']
                
                if events_collection and len(events_collection) > 0:
                    appointment_times = []
                    for event in events_collection:
                        # Handle both all-day events (date) and timed events (dateTime)
                        start_datetime = None
                        end_datetime = None
                        if 'start' in event:
                            if 'dateTime' in event['start']:
                                start_datetime = event['start']['dateTime']
                            elif 'date' in event['start']:
                                start_datetime = event['start']['date']
                        
                        if 'end' in event:
                            if 'dateTime' in event['end']:
                                end_datetime = event['end']['dateTime']
                            elif 'date' in event['end']:
                                end_datetime = event['end']['date']
                        
                        if start_datetime:
                            # Only include future appointments
                            if is_future_datetime(start_datetime):
                                formatted_time = format_datetime_range_human_readable(start_datetime, end_datetime)
                                appointment_times.append(formatted_time)
                    
                    # Set existing_appointment with formatted times
                    if appointment_times:
                        if existing_appointment:
                            existing_appointment += ", " + ", ".join(appointment_times)
                        else:
                            existing_appointment = ", ".join(appointment_times)
                    
                    # We have scheduled events, update description with this info
                    events_count = len([t for t in appointment_times])  # Count only future events
                    if events_count > 0:
                        calendar_info = f"Has {events_count} upcoming Google Calendar event"
                        calendar_info += "s" if events_count > 1 else ""
                        
                        if description:
                            description += f" {calendar_info}."
                        else:
                            description = calendar_info + "."
                else:
                    print("No upcoming Google Calendar events found.")
            except Exception as e:
                print(f"Error checking Google Calendar events: {str(e)}")
                print(traceback.format_exc())
                
        # Check for Outlook calendar events
        if self.agents[call_sid]['integrations'].get('outlook_connection_id'):
            # Check if there are any scheduled events for this user in Outlook Calendar
            print(f"Outlook Calendar connection ID: {self.agents[call_sid]['integrations']['outlook_connection_id']}")

            try:
                # Get events directly, NangoService's fetch_data for outlook events
                # will typically fetch from the default calendar if no calendar_id is specified.
                print(f"Fetching events from default Outlook calendar")
                events_result = await self.outlook_calendar_service.get_events(
                    self.agents[call_sid]['integrations']['outlook_connection_id']
                )
                
                # Display events in a well-formatted way
                print("\n=== OUTLOOK CALENDAR EVENTS ===")
                events_collection = []
                
                if events_result and 'records' in events_result:
                    events_collection = events_result['records']
                
                if events_collection and len(events_collection) > 0:
                    appointment_times = []
                    for event in events_collection:
                        print(f"\nEvent:")
                        print(f"  Subject: {event.get('subject', 'N/A')}")
                        
                        start_datetime = None
                        end_datetime = None
                        
                        if 'start' in event:
                            start = event['start'].get('dateTime', 'N/A')
                            timezone = event['start'].get('timeZone', 'N/A')
                            print(f"  Start: {start} ({timezone})")
                            if start != 'N/A':
                                start_datetime = start
                            
                        if 'end' in event:
                            end = event['end'].get('dateTime', 'N/A')
                            timezone = event['end'].get('timeZone', 'N/A')
                            print(f"  End: {end} ({timezone})")
                            if end != 'N/A':
                                end_datetime = end
                        
                        # Only include future appointments
                        if start_datetime and is_future_datetime(start_datetime):
                            formatted_time = format_datetime_range_human_readable(start_datetime, end_datetime)
                            appointment_times.append(formatted_time)
                            
                        print(f"  Location: {event.get('location', {}).get('displayName', 'N/A')}")
                        print(f"  Status: {event.get('showAs', 'N/A')}")
                        
                    print("===============================\n")
                    
                    # Set existing_appointment with formatted times
                    if appointment_times:
                        if existing_appointment:
                            existing_appointment += ", " + ", ".join(appointment_times)
                        else:
                            existing_appointment = ", ".join(appointment_times)
                    
                else:
                    print("No upcoming Outlook Calendar events found.")

            except Exception as e:
                print(f"Error checking Outlook Calendar events: {str(e)}")
                print(traceback.format_exc())

        if crmUserId is not None:
            self.agents[call_sid]['lead_id'] = crmUserId
            self.agents[call_sid]['previous_convo_summary'] = description

        return {"greetings" : greetings , "email": email ,"phone": phoneNumber ,"description" : description, "fullname" : fullname, "existing_appointment": existing_appointment}
    
    async def enable_background_sound(self ,call_id, status = False):
        self.sessions[call_id]['background_sound'] = status
        if status is True:
            if not self.twilio_service.background_sound:
                audio_stream = await self.twilio_service.get_background_sound()
                self.twilio_service.background_sound = audio_stream
            await self.twilio_service.send_audio_stream(self.sessions[call_id]['websocket'], call_id, self.twilio_service.background_sound)

    async def complete_status_callback(self, data):
        """Handle the stream callback to get the streamSid."""

        call_sid = data.get("CallSid")
        call_duration = data.get("CallDuration")
        call_direction = data.get("Direction")
        call_status = data.get("CallStatus")
        time_stamp = data.get("Timestamp")
        resolution_status= 'RESOLVED'
        agent_id = None
        # self.sessions[call_sid]['stream_sid'] = stream_sid
        if call_sid in self.agents and "id" in self.agents[call_sid]:
            agent_id = self.agents[call_sid]['id']

        if call_sid in self.agents and "route_call" in self.agents[call_sid] and self.agents[call_sid]['route_call'] == True:
            resolution_status = 'ROUTED'
            
        data= {
            "duration" : call_duration,
            "direction": call_direction,
            "status": call_status,
            "call_sid" : call_sid,
            "agent_id" : agent_id,
            "timestamp" : time_stamp,
            "resolution_status": resolution_status
        }
        
            
        await self.backend_service.update_call_info(data)

        if call_status in ["failed", "busy"]:
            # Ensure the call is fully disconnected
            self.twilio_service.client.calls(call_sid).update(status='completed')
            print(f"Call {call_sid} cleaned up.")
        if call_sid in self.agents:
            self.agents[call_sid]['complete_call'] = True
        self.flush_agent(call_sid)
        return "OK", 200
    
    def flush_agent(self, call_sid):
        if call_sid in self.agents and self.agents[call_sid]['complete_call'] == True and self.agents[call_sid]['websocket_closed'] == True:
            del self.agents[call_sid]
    
    async def fallback_status_callback(self, data):
        call_sid = data.get("CallSid")
        call_duration = data.get("CallDuration")
        call_direction = data.get("Direction")
        call_status = 'FAILED'
        time_stamp = data.get("Timestamp")
        resolution_status= 'FAILED'
        agent_id = None

        if call_sid in self.agents and "id" in self.agents[call_sid]:
            agent_id = self.agents[call_sid]['id']

        data= {
            "duration" : call_duration,
            "direction": call_direction,
            "status": call_status,
            "call_sid" : call_sid,
            "agent_id" : agent_id,
            "timestamp" : time_stamp,
            "resolution_status": resolution_status

        }

        self.twilio_service.client.calls(call_sid).update(status='completed')
        print(f"Call {call_sid} cleaned up.")

        await self.backend_service.update_call_info(data)
        
    async def get_nango_session_token(self, user_id, allowed_integrations=None):
        """Get a Nango session token for the frontend to use when connecting to third-party services
        
        Args:
            user_id: Unique identifier for the user
            allowed_integrations: List of integration IDs the user is allowed to connect to (optional) 
           
        """
        return await self.ai_service.get_nango_session_token(user_id, allowed_integrations)
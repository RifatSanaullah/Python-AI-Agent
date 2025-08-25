import base64
import audioop
import asyncio
import logging
import time, io
import numpy as np
from app.services.playht_service import PlayHT
from app.services.murf_service import MurfAI
from app.services.twilio_service import TwilioService
from app.services.ai_service import AIService
from app.services.voice_detector import VoiceActivityDetector
# from app.services.ai_service_v2 import AIService
from app.services.s3_service import S3Service
from app.services.backend_service import BackendHandler
from app.services.polly_service import PollyService
from app.services.deepgram_service import DeepgramService
from app.services.assembly_ai_transcribe_service import TranscribeService
from app.services.elevenlabs_service import ElevenLabsService
from app.services.pipertts_service import PiperService
from app.services.azure_service import AzureService
# from app.services.azure_tts_service import AzureService
from app.services.zoho_service import ZohoService
from app.services.hubspot_service import HubSpotService
from app.services.salesforce_service import SalesforceService
from app.services.calendly_service import CalendlyService
from app.services.google_calendar_service import GoogleCalendarService
from app.services.outlook_calendar_service import OutlookCalendarService
from websockets.exceptions import ConnectionClosedError, ConnectionClosedOK
from datetime import datetime, timezone
from app.helpers.utils import get_interrupt_message, convert_mulaw_to_wav
from pydub import AudioSegment
from threading import Timer
import numpy as np
import uuid
from io import BytesIO
import numpy as np
import soundfile as sf
import time , re
from app.utils.datetime_formatter import format_datetime_human_readable, format_datetime_range_human_readable, is_future_datetime, sort_and_group_appointments
import json, asyncio
from app.services.cinc_service import CincService # Import the new unified CincService class

from app.adapters.filler_manager import FillerManager
from app.helpers.utils import estimate_speech_duration, fast_downsample_mulaw
from scipy.signal import resample as scipy_resample # Import to avoid name conflict

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
        # self.azure_service = AzureService()
        self.zoho_service = ZohoService()
        self.hubspot_service = HubSpotService()
        self.salesforce_service = SalesforceService()
        self.calendly_service = CalendlyService()
        self.google_calendar_service = GoogleCalendarService()
        self.outlook_calendar_service = OutlookCalendarService()
        self.filler_mgr = FillerManager()
        self.cinc_service = CincService() # Initialize CINC Service instance
        # self.transcribe_service = TranscribeService(on_transcript=self.handle_transcript)
        self.sessions = {}
        self.agents = {}
        self.completed_sessions = {}
        self.timer = {}
        self.loop= asyncio.get_running_loop()
        self.prefetched_details = {}
        self.calls = {}
        self.additionalinfo = {}
        self.lock = {}

    async def _get_or_create_lock(self, call_sid):
        if call_sid not in self.locks:
            self.locks[call_sid] = asyncio.Lock()
        return self.locks[call_sid]

    def generate_call_sid_uuid(self):
        """Generate a call SID using UUID4 (most random)"""
        return f"CA{uuid.uuid4().hex}"

    def update_state_calls(self, phone):
        call_id = self.generate_call_sid_uuid()

        self.calls[phone] = call_id

        return call_id

    async def update_details(self, account_id, details, phone, agentPhone, pre_call_sid=None, init_service=True):
        if account_id and details :
            self.prefetched_details[account_id] = details
        formattedPhone= self.format_us_number_simple(phone)
        if not formattedPhone.startswith('+'):
            formattedPhone = "+" + formattedPhone
        call_id = self.update_state_calls(formattedPhone)
        data = {
            "call_sid" : call_id,
            "from" : agentPhone,
            "to" : formattedPhone,
            "application_sid" : None,
            "direction" : 'outbound-api',
            "isBoom": None,
            "pre_call_sid" : pre_call_sid
        }
        return await self.update_agent_data(call_id, data, init_service)


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
                if data['streamSid'] and data['streamSid'] not in self.sessions:
                    self.initialize_session_info(data['streamSid'], call_id)
                    session = self.sessions[data['streamSid']]
                if data['streamSid'] and self.agents[call_id]['websocket'] is None:

                    self.agents[call_id]['websocket'] = websocket
                    self.sessions[data['streamSid']]['agent'] = self.get_business_agent(call_id)
                    self.agents[call_id]['stream_sid'] = data['streamSid']

                    session = self.sessions[data['streamSid']]
          
                    if session['call_initialized'] == False:
                        await self.process_all_info(data['streamSid'], call_id)
                        self.sessions[data['streamSid']]['call_initialized'] = True
                    # if self.agents[data['streamSid']['call_sid']]['STT']['name'] == 'Deepgram':
                    #     session['transcribe_service'].establish_dg_connection(self.agents[data['streamSid']['call_sid']]['STT']['model'])
                    # else: session['transcribe_service'].connect()

                if data['streamSid'] not in self.sessions or 'call_sid' not in self.sessions[data['streamSid']]:
                    continue

                if (data['streamSid']
                and self.agents[call_id]['last_user_audio_time'] is not None
                and self.additionalinfo[self.agents[call_id]['call_sid']]['agent_call_in_queue'] is not True
                and time.time() - self.agents[call_id]['last_user_audio_time'] > self.agents[call_id]['silence_duration']):
                    print("Ending call due to prolonged silence...")
                    self.twilio_service.hangup_call(self.agents[call_id]['call_sid'])
                    self.agents[call_id]['last_user_audio_time'] = None
                    self.agents[call_id]['voicemail_detected'] = True
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

                    # result = await self.is_silent_or_empty_mulaw_numpy(chunk_bytes)
                    # is_audio_silent = result['is_silent']

                    # # is_audio_silent = await self.is_mulaw_stream_silent_base64(chunk_bytes)
                    # # is_audio_silent = result['is_silent']

                    # if not is_audio_silent:
                    #     # await self.on_user_speech(data['streamSid'])
                    #     self.sessions[data['streamSid']]['last_user_audio_time'] =  None
                    #     self.sessions[data['streamSid']]['wait_counter'] = 0

                    with open(output_file, "ab") as f:
                        f.write(chunk_bytes)

                    if (('route_call' not in self.agents[call_id] 
                        or self.agents[call_id]['route_call'] == False ) and
                        ( 'end_call' not in self.agents[call_id]
                        or self.agents[call_id]['end_call'] == False) ):
                        # voice_detected =  await self.agents[call_id]["VAD"].process_audio_chunk(chunk_bytes)
                        # if voice_detected:
                        #     print("voice_detected")
                        #     await self.on_user_speech(call_id)
                        await self.twilio_service.enqueue_audio(call_id, chunk_bytes ,'audio_buffer')


                if data['streamSid'] and not self.twilio_service.is_empty(call_id, 'response_buffer'):
                    # print("Processing response buffers...")
                    response_audio = await self.twilio_service.get_or_dequeue_audio(call_id, 'response_buffer')
                    # mulaw_audio = fast_downsample_mulaw(response_audio)
                    # self.agents[call_id]['ai_speaking'] = True
                    # await self.twilio_service.send_audio_stream(self.agents[call_id]['websocket'], data['streamSid'], response_audio)
                    # await self.twilio_service.send_control_command(session['websocket'], 'stop')
                    if self.sessions[data['streamSid']]['background_sound'] is True:
                        await self.stop_stream(call_id)
                    # session['ai_speaking'] = True
                    with open(output_file, "ab") as f:
                        f.write(response_audio)

                if data['streamSid'] and call_id and not self.twilio_service.is_empty(call_id, 'audio_buffer'):
                    audio_data = await self.twilio_service.get_or_dequeue_audio(call_id, 'audio_buffer')
                    # await self.transcribe_service.transcribe(audio_data)
                    # await session['synthesis_service'].transcribe(audio_data)
                    await self.agents[call_id]['transcribe_service'].transcribe(audio_data)

        except ConnectionClosedError as e:
            print(f"Connection closed with error: {e.code} - {e.reason}")
            if self.agents[call_id].get('synthesis_service') is not None:
                await self.agents[call_id]['synthesis_service'].disconnect()
            if self.agents[call_id].get('transcribe_service') is not None:
                await self.agents[call_id]['transcribe_service'].disconnect()  # Close the transcriber service
                    
        except ConnectionClosedOK as e:
            print(f"Connection closed normally: {e.code} - {e.reason}")
        except Exception as e:
            print("Unexpected error:", e)
        finally:
            print("WebSocket connection closed.")
            if self.agents[call_id]['STT']['name'] == 'Deepgram' and self.agents[call_id]['transcribe_service']:
                self.agents[call_id]['transcribe_service'].cancel_transmit()
            if call_id in self.ai_service.conversations:
                conversations = self.ai_service.conversations[call_id]

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
                    "lead_appointment_id": self.agents[call_id].get('lead_appointment_id', None),
                }

                try:
                    response = await self.backend_service.update_conversation_info(data)
                    isBoom = self.agents[call_id]['isBoom']
                    print("summary", response.get('summary'))
                    print("isBoom" , isBoom)
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


                self.ai_service.close_conversation(call_id)
                self.twilio_service.remove_stream_from_queue(call_id)
                self.agents[call_id]['websocket_closed'] = True
                # self.flush_agent(call_id)
            if call_id in self.agents and self.agents[call_id].get('synthesis_service') is not None:
                await self.agents[call_id]['synthesis_service'].disconnect()
            if call_id in self.agents and self.agents[call_id].get('transcribe_service') is not None:
                await self.agents[call_id]['transcribe_service'].disconnect()  # Close the transcriber service
                    
            del self.sessions[session['stream_sid']]
            if call_id in self.agents:
                del self.agents[call_id]
            self.clear_timer(call_id)
            try:
                await websocket.close()
            except Exception as e:
                print("--Websocket connection Closed--")
    
    async def update_crm_data(self,call_id, lead_id: str, integrations, summary, appointment, prev_event_id, previous_convo_summary):
        # Log the integrations dictionary
        logging.info(f"Integrations for call {call_id}: {integrations}")
        event = appointment.get('eventData') if appointment else None
        calendarEventData = appointment.get('calendarEventData') if appointment else None
        # Get session info to extract account_id and connection_id for CINC
        session_info = self.get_business_agent(call_id)
        account_id = session_info.get("account_id") # This should be the account ID from the database
        cinc_connection_id = session_info.get("integrations", {}).get("cinc_connection_id") # Get CINC specific connection_id
        
        print(f"DEBUG - update_crm_data: account_id={account_id}, cinc_connection_id={cinc_connection_id}")

        # CINC Integration
        # Check if CINC is available by connection_id existence
        if cinc_connection_id and cinc_connection_id != "null" and cinc_connection_id != "" and account_id:
            try:
                logging.info(f"Processing CINC integration for account {account_id} with connection {cinc_connection_id}")
                
                # Check if summary has CINC data structure (cincLeadPostFormat or cincLeadPatchFormat)
                cinc_data = None
                if summary and isinstance(summary, dict):
                    # Look for CINC format data in summary
                    if 'info' in summary and 'contact' in summary['info']:
                        cinc_data = summary.copy()
                        
                        # Get call logs from multiple sources
                        description = cinc_data.get('Description', '') or cinc_data.get('description', '')
                        call_logs = cinc_data.get('CallLogs', '') or cinc_data.get('call_logs', '')
                        
                        # Remove these fields as they will be converted to notes
                        cinc_data.pop('Description', None)
                        cinc_data.pop('description', None)
                        cinc_data.pop('CallLogs', None)
                        cinc_data.pop('call_logs', None)
                        
                        # Create notes array - ALWAYS include both CallLogs and Description as separate notes
                        notes_array = []
                        
                        # Add CallLogs note if available
                        if call_logs and call_logs.strip():
                            notes_array.append({
                                "content": call_logs,
                                "category": "call",
                                "is_pinned": True,
                                "created_by": "Verbacall",
                            })
                        
                        # ALWAYS add Description note if available (regardless of CallLogs content)
                        if description and description.strip():
                            notes_array.append({
                                "content": description,
                                "category": "general", 
                                "is_pinned": True,
                                "created_by": "Verbacall",
                            })
                        
                        # Add notes array to CINC data if we have any notes
                        if notes_array:
                            cinc_data["notes"] = notes_array
                    else:
                        # If summary doesn't have CINC format, create basic structure
                        description = summary.get('Description', '') or summary.get('description', '')
                        call_logs = summary.get('CallLogs', '') or summary.get('call_logs', '')
                        
                        cinc_data = {
                            "info": {
                                "contact": {
                                    "email": summary.get('email', ''),
                                    "first_name": summary.get('first_name', ''),
                                    "last_name": summary.get('last_name', ''),
                                    "phone_numbers": {
                                        "cell_phone": summary.get('phone', '') or summary.get('cell_phone', ''),
                                        "home_phone": summary.get('home_phone', ''),
                                    }
                                },
                                "is_buyer": summary.get('is_buyer', True),  # Default to buyer for real estate
                                "is_seller": summary.get('is_seller', False),
                                "source": summary.get('source', 'AI Call Assistant'),
                                "status": 'contacted' if lead_id else 'unworked',
                            },
                            "pipeline": summary.get('pipeline', {}),
                            "timezone": summary.get('timezone', 'America/New_York'),
                        }
                        
                        # Create notes array - ALWAYS include both CallLogs and Description as separate notes
                        notes_array = []
                        
                        # Add CallLogs note if available
                        if call_logs and call_logs.strip():
                            notes_array.append({
                                "content": call_logs,
                                "category": "call",
                                "is_pinned": True,
                                "created_by": "Verbacall",
                            })
                        
                        # ALWAYS add Description note if available (regardless of CallLogs content)
                        if description and description.strip():
                            notes_array.append({
                                "content": description,
                                "category": "call",
                                "is_pinned": True,
                                "created_by": "Verbacall",
                            })
                        
                        # Add notes array to CINC data if we have any notes
                        if notes_array:
                            cinc_data["notes"] = notes_array
                
                # Ensure required email field is present

                # Determine if we should create or update based on lead_id or email/phone search
                should_create_new = True
                existing_lead_id = lead_id
                
                # If no lead_id provided, try to find existing lead by phone or email
                if not lead_id or lead_id == "null" or lead_id == "":
                    try:
                        email = cinc_data['info']['contact']['email']
                        phone = cinc_data['info']['contact'].get('phone_numbers', {}).get('cell_phone', '')
                        
                        # Try to find existing lead by phone first (if phone available)
                        if phone:
                            existing_leads = await self.cinc_service.get_leads(
                                account_id=account_id,
                                connection_id=cinc_connection_id,
                                phone=phone
                            )
                            if existing_leads and isinstance(existing_leads, dict) and existing_leads.get('leads'):
                                existing_lead_id = existing_leads['leads'][0]['id']
                                should_create_new = False
                                logging.info(f"Found existing CINC lead by phone: {existing_lead_id}")
                                
                        # If not found by phone, try by email (CINC API may not support email search directly)
                        # For now, we'll proceed with create if not found by phone
                                
                    except Exception as search_error:
                        logging.warning(f"Error searching for existing CINC lead: {search_error}")
                else:
                    should_create_new = False  # We have a lead_id, so update existing
                
                if not should_create_new and existing_lead_id:
                    # Update existing lead
                    logging.info(f"Updating CINC lead {existing_lead_id}")
                    if self.agents[call_id]['voicemail_detected'] is True:
                        print("Voicemail detected, updating status to unworked")
                        cinc_data['info']['status'] = "unworked"
                        cinc_data['pipeline']['history'].pop()
                        cinc_data['pipeline']['history'].append({
                            "stage": "Attempted Contact",
                            "staged_date": datetime.now(timezone.utc).isoformat(),    
                        })
                    result = await self.cinc_service.update_lead(
                        account_id=account_id,
                        lead_id=existing_lead_id,
                        lead_data=cinc_data,
                        connection_id=cinc_connection_id
                    )
                    logging.info(f"CINC lead updated successfully: {result}")
                else:
                    # Create new lead
                    if not cinc_data or not cinc_data.get('info', {}).get('contact', {}).get('email'):
                        logging.warning("CINC integration skipped: No email address found in summary")
                    else:
                        logging.info("Creating new CINC lead")
                        result = await self.cinc_service.create_lead(
                            account_id=account_id,
                            lead_data=cinc_data,
                            connection_id=cinc_connection_id
                        )
                        logging.info(f"CINC lead created successfully: {result}")
                        
                        # Extract lead ID from response for future updates
                        if result and isinstance(result, dict):
                            new_lead_id = result.get('body', {}).get('id') or result.get('id')
                            if new_lead_id:
                                logging.info(f"New CINC lead ID: {new_lead_id}")
                            
            except Exception as e:
                logging.error(f"Error in CINC integration for account {account_id}: {str(e)}")
                # Continue with other integrations even if CINC fails

        if integrations and integrations["hubspot_connection_id"] is not None and integrations["hubspot_connection_id"] != '':
            summary["email"] = summary['email'].replace(" ", "")
            summary["phone"] = self.format_us_number_simple(summary["phone"])
            if summary['phone'] != self.agents[call_id]['leadbound']:
                summary['mobilephone'] = self.format_us_number_simple(self.agents[call_id]['leadbound'])
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
                    summary['phone'] = self.format_us_number_simple(self.agents[call_id]['leadbound'])
                summary = self.remove_empty_values(summary)
                body = {
                    'contact' : summary,
                    'note' : notes
                }
                await self.ai_service.hubspot_service.store_leads(integrations['hubspot_connection_id'], body)
                

        if integrations and integrations["salesforce_connection_id"] is not None and integrations["salesforce_connection_id"] != '':
            summary["Email"] = summary['Email'].replace(" ", "").replace(",",'')
            summary["Phone"] = self.formatToSalesforceNumber(summary["Phone"])
            if summary['Phone'] != self.agents[call_id]['leadbound']:
                summary['MobilePhone'] = self.formatToSalesforceNumber(self.agents[call_id]['leadbound'])
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
                            summary['Phone'] = self.formatToSalesforceNumber(self.agents[call_id]['leadbound'])
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
            if summary['Phone'] != self.agents[call_id]['leadbound']:
                summary['Mobile'] = self.format_us_number_simple(self.agents[call_id]['leadbound'])
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
                            summary['Phone'] = self.format_us_number_simple(self.agents[call_id]['leadbound'])
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
                print(f"DEBUG - Calendar Event Data Type: {type(calendarEventData)}")
                print(f"DEBUG - Calendar Event Data: {calendarEventData}")
                
                if calendarEventData is not None and calendarEventData != '' and isinstance(calendarEventData, dict):
                    # Validate required fields
                    required_fields = ["subject", "startDateTime", "endDateTime"]
                    missing_fields = [field for field in required_fields if not calendarEventData.get(field)]
                    
                    if missing_fields:
                        logging.warning(f"Missing required fields for Google Calendar: {missing_fields}")
                        logging.warning(f"Calendar event data: {calendarEventData}")
                    else:
                        # Prepare Google Calendar event payload (using timezone-aware datetime)
                        google_event_payload = {
                        "summary": calendarEventData.get("subject"),
                        "description": calendarEventData.get("description"),
                        "location": calendarEventData.get("location", ""),
                        "start": {
                            "dateTime": calendarEventData.get('startDateTime'),
                            "timeZone": calendarEventData.get("timezone", "America/New_York")
                        },
                        "end": {
                            "dateTime": calendarEventData.get('endDateTime'),
                            "timeZone": calendarEventData.get("timezone", "America/New_York")
                        }
                    }

                    # Handle appointment operations with proper priority: delete > update > create
                    if appointment.get('deleteAppointment'):
                        # Delete existing appointment
                        # Use stored event ID from agent initialization
                        google_calendar_event_id = self.agents.get(call_id, {}).get('google_calendar_event_id')
                        
                        print(f"DEBUG - Google Calendar Delete: stored_id={google_calendar_event_id}")
                        
                        if google_calendar_event_id:
                            logging.info(f"Deleting Google Calendar event: {google_calendar_event_id}")
                            await self.google_calendar_service.delete_event(
                                integrations['google_calendar_connection_id'],
                                google_calendar_event_id
                            )
                            logging.info(f"Google Calendar event deleted successfully")
                        else:
                            logging.warning("Google Calendar event ID not found for deletion")
                    elif appointment.get('updateAppointment'):
                        # Update existing appointment
                        # Use stored event ID from agent initialization
                        google_calendar_event_id = self.agents.get(call_id, {}).get('google_calendar_event_id')
                        
                        
                        print(f"DEBUG - Google Calendar Update: stored_id={google_calendar_event_id}")
                        
                        if google_calendar_event_id:
                            logging.info(f"Updating Google Calendar event: {google_calendar_event_id}")
                            
                            # For updates, only send essential fields (start and end time)
                            google_update_payload = {
                                "start": {
                                    "dateTime": calendarEventData.get('startDateTime'),
                                    "timeZone": calendarEventData.get("timezone", "America/New_York")
                                },
                                "end": {
                                    "dateTime": calendarEventData.get('endDateTime'),
                                    "timeZone": calendarEventData.get("timezone", "America/New_York")
                                },
                                "summary": calendarEventData.get("subject"),  # Add this
                                "description": calendarEventData.get("description"),  # Add this
                                "status": "confirmed"  # Add this to prevent cancellation
                            }
                            
                            if google_update_payload and google_update_payload.get("start") and google_update_payload.get("end"):
                                print(f"DEBUG - Google Calendar Update Payload: {google_update_payload}")
                                response = await self.google_calendar_service.update_event(
                                    integrations['google_calendar_connection_id'],
                                    google_calendar_event_id,
                                    google_update_payload
                                )
                                logging.info(f"Google Calendar event time updated successfully: {response}")
                            else:
                                logging.warning(f"Invalid payload for Google Calendar event update: {google_update_payload}")
                                logging.warning("Missing required fields: start, end, or payload is empty")
                        else:
                            logging.warning("Google Calendar event ID not found for update")
                    elif appointment.get('newAppointment'):
                        # Create new appointment
                        response = await self.google_calendar_service.create_event(
                            integrations['google_calendar_connection_id'],
                            google_event_payload
                        )
                        if response and 'id' in response and 'id' in appointment:
                            appointment_id = appointment['id']  # BoomersHub internal appointment ID
                            await self.backend_service.update_appointment({
                                "appointment_id": appointment_id,
                                "google_calendar_event_id": response['id']  # Storing Google Calendar event ID
                            })
                        elif response:
                            pass  # Response without ID
                        else:
                            pass  # No response
            except Exception as e:
                logging.error(f"Error in Google Calendar event handling: {str(e)}")
                import traceback
                traceback.print_exc()
                import traceback

        # Outlook Calendar Event Handling
        if integrations and integrations.get("outlook_connection_id") and integrations["outlook_connection_id"] != '':
            try:
                print(f"DEBUG - Outlook Calendar Event Data: {calendarEventData}")
                
                if calendarEventData is not None and calendarEventData != '' and isinstance(calendarEventData, dict):
                    # Validate required fields
                    required_fields = ["subject", "startDateTime", "endDateTime", "timezone"]
                    missing_fields = [field for field in required_fields if not calendarEventData.get(field)]
                    
                    if missing_fields:
                        logging.warning(f"Missing required fields for Outlook Calendar: {missing_fields}")
                        logging.warning(f"Calendar event data: {calendarEventData}")
                    else:                     
                        # Transform event data to the format expected by the Nango script's 'fields'
                        # Prepare attendees array from the calendar event data
                        attendees = []
                        if calendarEventData.get("attendeeEmail"):
                            attendees.append(calendarEventData.get("attendeeEmail"))
                        
                        outlook_event_payload = {
                            "subject": calendarEventData.get("subject"),
                            "description": calendarEventData.get("description"),
                            "location": calendarEventData.get("location", ""),
                            "startDateTime": calendarEventData.get('startDateTime'), # Expected as ISO 8601 string
                            "endDateTime": calendarEventData.get('endDateTime'),     # Expected as ISO 8601 string
                            "timeZone": calendarEventData.get("timezone"), # IANA timezone 
                            "attendees": attendees  # Provide actual attendees array from event data
                        }
                        
                        # Handle appointment operations with proper priority: delete > update > create
                        if appointment.get('deleteAppointment'):
                            # Delete existing appointment
                            # Use stored event ID from agent initialization
                            outlook_calendar_event_id = self.agents.get(call_id, {}).get('outlook_calendar_event_id')
                            
                            print(f"DEBUG - Outlook Calendar Delete: stored_id={outlook_calendar_event_id}")
                            
                            if outlook_calendar_event_id:
                                logging.info(f"Deleting Outlook Calendar event: {outlook_calendar_event_id}")
                                await self.outlook_calendar_service.delete_event(
                                    integrations['outlook_connection_id'],
                                    outlook_calendar_event_id
                                )
                                logging.info(f"Outlook Calendar event deleted successfully")
                            else:
                                logging.warning("Outlook Calendar event ID not found for deletion")
                        elif appointment.get('updateAppointment'):
                            # Update existing appointment
                            # Use stored event ID from agent initialization
                            outlook_calendar_event_id = self.agents.get(call_id, {}).get('outlook_calendar_event_id')
                            
                            print(f"DEBUG - Outlook Calendar Update: stored_id={outlook_calendar_event_id}")
                            
                            if outlook_calendar_event_id:
                                logging.info(f"Updating Outlook Calendar event: {outlook_calendar_event_id}")
                                
                                # For updates, only send essential fields (start and end time)
                                outlook_update_payload = {
                                    "start": {
                                        "dateTime": calendarEventData.get('startDateTime'),
                                        "timeZone": calendarEventData.get("timezone", "America/New_York")
                                    },
                                    "end": {
                                        "dateTime": calendarEventData.get('endDateTime'),
                                        "timeZone": calendarEventData.get("timezone", "America/New_York")
                                    },
                                    "subject": calendarEventData.get("subject"),  # Add this
                                    "body": {  # Add this
                                        "contentType": "html",
                                        "content": calendarEventData.get("description", "")
                                    }
                                }
                                
                                # Only update if we have the required fields
                                if outlook_update_payload.get("start") and outlook_update_payload.get("end"):
                                    print(f"DEBUG - Outlook Calendar Update Payload: {outlook_update_payload}")
                                    response = await self.outlook_calendar_service.update_event(
                                        integrations['outlook_connection_id'],
                                        outlook_calendar_event_id,
                                        outlook_update_payload
                                    )
                                    logging.info(f"Outlook Calendar event time updated successfully: {response}")
                                else:
                                    logging.warning(f"Invalid payload for Outlook Calendar event update: {outlook_update_payload}")
                                    logging.warning("Missing required fields: start or end objects")
                            else:
                                logging.warning("Outlook Calendar event ID not found for update")
                        elif appointment.get('newAppointment'):
                            # Create new appointment
                            response = await self.outlook_calendar_service.create_event(
                                integrations['outlook_connection_id'],
                                outlook_event_payload
                            )
                            if response and 'id' in response and 'id' in appointment:
                                appointment_id = appointment['id']
                                await self.backend_service.update_appointment({
                                    "appointment_id": appointment_id,
                                    "outlook_calendar_event_id": response['id']
                                })
                            elif response:
                                pass  # Response without ID
                            else:
                                pass  # No response
                else:
                    logging.warning("Missing required fields for Outlook Calendar event")
                    logging.warning(f"Calendar event data: {calendarEventData}")
            except Exception as e:
                logging.error(f"Error in Outlook Calendar event handling: {str(e)}")
                import traceback
                traceback.print_exc()


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

    def initialize_transcriber(self, call_sid, Service : TranscribeService | DeepgramService):
        """Initialize transcriber with bound methods for handling transcripts and user speech."""
        return Service(
            on_transcript=self.create_on_transcript_handler(call_sid),
            on_start=self.create_on_user_speech_handler(call_sid),
            loop= self.loop,
            speak_model = self.agents[call_sid]['TTS']['voice']['model']
        )

    def create_on_transcript_handler(self, call_id):
        """Return a callback method for handling transcripts."""
        async def handler(transcript: str):
            await self.handle_transcript(transcript, call_id)
        return handler

    def create_on_user_speech_handler(self, call_id):
        """Return a callback method for handling user speech start."""
        async def handler():
            await self.on_user_speech(call_id)
        return handler 
               
    async def stop_stream(self,call_id):
        # await asyncio.sleep(1)  # Wait for 1 second
        await self.twilio_service.stop_audio_stream(self.agents[call_id]['websocket'], self.agents[call_id]['stream_sid'])
        self.agents[call_id]['ai_interrupt'] =  True
        self.ai_service.update_interrupt_status(call_id, True)
        await self.agents[call_id]["synthesis_service"].update_tts_interrupt(True)
        self.agents[call_id]['background_sound'] = False
        return

    async def on_user_speech(self, call_id):
        self.agents[call_id]['last_user_audio_time'] = None
        if self.agents[call_id].get('transmit_task', None) is not None:
            print("Cancelling transmit task for call_id")
            self.agents[call_id]['transmit_task'].cancel()
            self.agents[call_id]['transmit_task'] = None
        if call_id in self.agents and self.agents[call_id]['user_speaking'] is not True:
            self.agents[call_id]['user_speaking'] = True
            await self.stop_stream(call_id)
            self.agents[call_id]['ai_speaking'] = False
        return

    def contains_any_word(self, text:str):
        # Check if any word in the array exists in the text
        word_list = ['Bye','Goodbye','Have a nice day','Have a great day','Have a wonderful day']
        return any(word.lower() in text.lower() for word in word_list)
    
    async def handle_transcript(self, transcript, call_id):
        print(f"Transcript: {transcript}")
        # await self.enable_background_sound(call_id, True)
        if call_id not in self.agents or 'stream_sid' not in self.agents[call_id]:
            return
        self.agents[call_id]['ai_interrupt'] =  False
        self.agents[call_id]['user_speaking'] = False
        # self.ai_service.update_interrupt_status(call_id, False)

        # filler_audio = self.filler_mgr.next()
        # await self.synthesize_response(filler_audio, call_id)
        # self.sessions[call_id]['prev_wait_duration'] = 0
        # self.sessions[call_id]['wait_duration'] = 0
        streamingResponse = True
        # if self.agents[call_id]['TTS']['name'] == 'Elevenlabs':
        #     streamingResponse = False
        response = await self.ai_service.generate_response(call_id, transcript, self.synthesize_response, self.agents[call_id]['aiClient'], self.agents[call_id]['synthesis_service'].flush_sp_ws, streamingResponse)
        print(f"Response: {response}")
        estamitate_result = await estimate_speech_duration(response, 180)
        self.agents[call_id]['last_user_audio_time'] = time.time() + (estamitate_result['total_seconds'])

        if 'End Call Message' in response  or  self.contains_any_word(response):
            self.agents[call_id]['end_call'] = True
            response = response.replace('End Call Message', '')
            # Schedule the call to end after 2 seconds
            # wait_time = self.sessions[call_id]['wait_duration']
            # if self.sessions[call_id]['last_transcript_time']:
            print("estamitate_result: ", estamitate_result)
            wait_time = estamitate_result['total_seconds'] + 1
            # wait_time = self.sessions[call_id]['wait_duration'] + self.sessions[call_id]['prev_wait_duration']
            # wait_time = 15
            print("wait_time: ", wait_time)
            self.clear_timer(call_id)
            self.timer[call_id] = Timer(wait_time, self.twilio_service.hangup_call, args=[self.agents[call_id]['call_sid']])
            self.timer[call_id].start()
            
        if 'Routing Message' in response or 'connecting the call with a real agent' in response  or 'connect you with a real agent' in response  or 'getting a real agent on the line for you' in response  or 'connecting you to a real agent' in response  or 'hold on' in response or 'hang-on' in response or 'hang on' in response or 'hang tight' in response  or 'hang-tight' in response:
            response = response.replace('Routing Message', '')

            wait_time = estamitate_result['total_seconds']

            if self.additionalinfo[self.agents[call_id]['call_sid']]['agent_call_in_queue'] is not True:
                await asyncio.sleep(2)
                await self.process_agent_call(call_id)
                
                # print(call)



                # self.agents[call_id]['route_call'] = True

            # Schedule the call to end after 2 seconds
            # self.clear_timer(call_id)
            # self.timer[call_id] = Timer(13, self.twilio_service.redirect_call,
            #               args=[
            #                 self.sessions[call_id]['call_sid'],
            #                 self.agents[self.sessions[call_id]['call_sid']]['routingInfo']['routingNumber'],
            #                 self.call_routed
            #                 ]
            #             )
            # self.timer[call_id].start()
        # self.sessions[call_id]['prev_wait_duration'] = 0
        # self.sessions[call_id]['wait_duration'] = 0

        elif  'Transferring message' in response or 'transferring-message' in response or 'Transferring Message' in response or "You're now connected" in response or "You’re now connected" in response or "You are now connected" in response or 'The person has connected on the call right now' in response or 'The person is on the line' in response or 'The person is on the call right now' in response or 'The person is on the line right now' in response:

            self.agents[call_id]['route_call'] = True
            await self.establish_tts(response, self.agents[call_id]['pre_call_sid'])
            wait_time = estamitate_result['total_seconds']
            await asyncio.sleep(wait_time)
            self.twilio_service.update_call(self.agents[call_id]['pre_call_sid'], f"conf_{self.agents[call_id]['pre_call_sid']}")
            self.twilio_service.update_call(self.agents[call_id]['call_sid'], f"conf_{self.agents[call_id]['pre_call_sid']}")

        if 'will not be transferred' in response or "won't be transferred" in response or "won’t be transferred" in response or "won’t transfer" in response or "won't transfer" in response:
            await self.establish_tts("The agent is busy right now. Will connect you later. Would you like to appointment instead?", self.agents[call_id]['pre_call_sid'])
            self.agents[self.additionalinfo[self.agents[call_id]['pre_call_sid']]['call_id']]['route_call'] = False



        # await self.synthesize_response(response, call_id)
        self.agents[call_id]['last_transcript_time'] = time.time()

    async def process_agent_call(self, call_id):
            
            summary = await self.ai_service.get_summary(call_id)
            self.agents[call_id]['summary'] = summary

            call_from = self.agents[call_id]['to']
            if self.agents[call_id]['direction'] == 'outbound-api':
                call_from = self.agents[call_id]['from']
            lead_routing_phone = self.agents[call_id].get('lead_routing_phone', None)
            if lead_routing_phone:
                await self.update_details(None, None, lead_routing_phone, call_from, self.agents[call_id]['call_sid'], False)
                # await asyncio.sleep(wait_time - 2)
                call = self.twilio_service.call_agent(
                    agent_number=lead_routing_phone,
                    # agent_number=self.agents[call_id]['routingInfo']['routingNumber'],
                    # agent_number="+16313494110",
                    twilio_number=call_from,
                    call_sid=self.agents[call_id]['call_sid'])
                
                self.additionalinfo[self.agents[call_id]['call_sid']]['agent_call_in_queue'] =  True

    def clear_timer(self,call_id):
        if call_id in self.timer:
            self.timer[call_id].cancel()
            self.timer[call_id] = None

    def call_routed(self, call_id):
        self.agents[call_id]['route_call'] = True
        self.additionalinfo[self.agents[call_id]['call_sid']]['route_call'] = True

    async def get_agent_knowledge(self, call_id):
        lead_routing_phone = self.agents[call_id].get('lead_routing_phone', None)
        if lead_routing_phone and ('pre_call_sid' not in self.agents[call_id] or not self.agents[call_id]['pre_call_sid'] or self.agents[call_id]['pre_call_sid'] is None):
            self.agents[call_id]['aiInstructions'] += f"""
            If the caller requests a transfer or want to connect/talk/discuss/meet with agent now treat it as confirmation and respond with:
                "Routing Message: I am connecting the call with a real agent. Please hold on and in the meantime do you have anything to query?"
                """
        data =  {        
            "knowledge" : self.agents[call_id]['knowledge'],
            "aiInstructions" : self.agents[call_id]['aiInstructions'],
            "agentName" : self.agents[call_id]['name'],
            "gender" : self.agents[call_id]['TTS']['voice']['gender'],
            "integrations" : self.agents[call_id]['integrations'],
            "new_knowledge" : self.agents[call_id]['new_knowledge'],
        }
        self.agents[call_id]['knowledge'] = None
        self.agents[call_id]['aiInstructions'] = None
        return data
    
    async def synthesize_response(self, text: str, call_id, chunk_id = None, is_greeting=False):
        session = self.agents.get(call_id)
        if not session or not text or text == '':
            return
        
        # start_time = datetime.now()
        model = self.agents[call_id]['TTS']['voice']['model']

        # if self.agents[call_id]['TTS']['name'] == 'Elevenlabs':
        #     await self.agents[call_id]["synthesis_service"].stream_text_to_speech(text)
        # else :
        if is_greeting is True:
            await self.agents[call_id]['synthesis_service'].send_stream_to_tts(text, "Greeting")
        else:
            await self.agents[call_id]["synthesis_service"].stream_text_to_speech(text, chunk_id)
        return


    async def queue_audio(self, call_id, audio_stream, chunk_id=None):
        session = self.agents.get(call_id)
        if not session :
            return
        interupted = session.get('ai_interrupt', False)
        ai_interupted = self.ai_service.get_interrupt_status(call_id, chunk_id)
        if not ai_interupted and  not interupted and self.agents[call_id]['user_speaking'] is not True:
            self.agents[call_id]['ai_speaking'] = True
            await self.twilio_service.send_audio_stream(session['websocket'], self.agents[call_id]['stream_sid'], audio_stream)
            await self.twilio_service.enqueue_audio(call_id, audio_stream ,'response_buffer')

    def initialize_session_info(self, stream_sid, call_sid):
        # Initialize a session for this specific call
        
        self.sessions[stream_sid] = {
                "ai_speaking": False,
                "ai_interrupt": False,
                "wait_counter": 0,
                "prev_wait_duration": 0,
                "stream_sid": stream_sid,
                "background_sound": None,
                "websocket" : None,
                "call_sid" : call_sid,
                "call_initialized" : False
            }

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


    async def update_agent_data(self, call_id, data , init_service=True):
        if call_id in self.agents:
            return
        api_response = await self.backend_service.create_call_info(data)
        
        # Debug logging for greeting selection
        print(f"=== PYTHON HANDLER DEBUG - Agent Data ===")
        print(f"Call ID: {call_id}")
        print(f"Call Direction: {data['direction']}")
        print(f"Backend Response Keys: {list(api_response.get('data', {}).keys())}")
        print(f"Agent Keys: {list(api_response.get('data', {}).get('agent', {}).keys())}")
        
        self.agents[call_id] = api_response['data']['agent']
        self.agents[call_id]['silence_duration'] = 15
        self.agents[call_id]['lead_routing_phone'] = None
        routing_number = self.agents[call_id]['routingInfo'].get('routingNumber', None)
        if routing_number is not None:
            self.agents[call_id]['lead_routing_phone'] = routing_number

        print('=== PYTHON HANDLER DEBUG - Agent Data ===')
        self.agents[call_id]['last_user_audio_time'] = None
        self.agents[call_id]['voicemail_detected'] = False
        self.agents[call_id]['isBoom'] = data['isBoom']
        self.agents[call_id]['complete_call'] = False
        self.agents[call_id]['websocket_closed'] = False
        self.agents[call_id]['end_call'] = False
        self.agents[call_id]['route_call'] = False
        self.agents[call_id]['from'] = data['from']
        self.agents[call_id]['to'] = data['to']
        # Determine leadbound number based on call direction
        self.agents[call_id]['direction'] = data['direction']
        if data['direction'] == 'outbound-api':
            self.agents[call_id]['leadbound'] = data['to']
        else:
            self.agents[call_id]['leadbound'] = data['from']
        self.agents[call_id]['previous_convo_summary'] = None
        self.agents[call_id]['new_knowledge'] = False
        self.agents[call_id]['aiClient'] = api_response['data']['aiClient']
        self.agents[call_id]['STT'] = api_response['data']['STT']
        self.agents[call_id]['TTS'] = api_response['data']['TTS']
        
        # Store new fields for BIDIRECTIONAL agent support
        self.agents[call_id]['handleCallType'] = api_response['data'].get('handleCallType', self.agents[call_id].get('type', 'INBOUND'))
        self.agents[call_id]['callDirection'] = api_response['data'].get('callDirection', 'inbound')

        print(f"Handle Call Type: {self.agents[call_id]['handleCallType']}")
        print(f"Call Direction: {self.agents[call_id]['callDirection']}")
        print(f"Agent Greetings: {self.agents[call_id].get('greetings', 'NOT FOUND')}")
        print(f"=== END PYTHON DEBUG ===")

        # Add timezone from backend response
        if 'agent' in api_response['data'] and 'timezone' in api_response['data']['agent']:
            self.agents[call_id]['timezone'] = api_response['data']['agent']['timezone']
        else:
            self.agents[call_id]['timezone'] = 'UTC'  # Default to UTC if not provided
        print(f"DEBUG - Agent timezone: {self.agents[call_id]['timezone']}")

        self.agents[call_id]['appointment'] = api_response['data']['appointment']
        print(f"xxxxDEBUGxxxxx - Appointment data: {self.agents[call_id]['appointment']}")
        # Extract and store calendar event IDs from the backend response, if available
        appointment_data = api_response['data'].get('appointment', {})
        google_calendar_event_id = appointment_data.get('googleCalendarEventId')
        outlook_calendar_event_id = appointment_data.get('outlookCalendarEventId')
        lead_appointment_id = appointment_data.get('appointmentId')

        print(f"xxxxDEBUGxxxxx - Google Calendar Event ID: {google_calendar_event_id}")
        print(f"xxxxDEBUGxxxxx - Outlook Calendar Event ID: {outlook_calendar_event_id}")

        # Store these IDs in the agent for easy access later
        self.agents[call_id]['google_calendar_event_id'] = google_calendar_event_id
        self.agents[call_id]['outlook_calendar_event_id'] = outlook_calendar_event_id
        self.agents[call_id]['lead_appointment_id'] = lead_appointment_id
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
            
        fullname = None
        email = None
        phone = None
        description = None
        existing_appointment = None
        greetings = self.agents[call_id]['greetings']
        if data.get('pre_call_sid'):
            self.agents[call_id]['pre_call_sid'] = data['pre_call_sid']
            call_uid = self.additionalinfo.get(data['pre_call_sid'], {}).get('call_id', None)
            pre_summary = self.agents.get(call_uid, {}).get('summary', None)
            self.agents[call_id]['pre_summary'] = pre_summary
            if self.agents[call_id]['pre_summary'] is not None and self.agents[call_id]['pre_summary'] != "":
                print("Found pre_summary: ", self.agents[call_id]['pre_summary'])
                self.agents[call_id]['knowledge'] = [{ 
                    "type" : "Business",
                    "content" : """Your main goal is to make a hot transfer to a live user who is waiting to connect with you. You cannnot give other information instead of the call summary.  """}]
                self.agents[call_id]['aiInstructions'] = f"""
                        You are the AI assistant who just finished speaking with a real estate lead and are now making a live transfer to a human agent. Based on your conversation with the lead, generate a 2-3 line spoken summary that you, the AI, will say right after the human agent picks up the phone.
                                After greetings from user or assistant, give the below summary within 2 or 3 lines.
                                The summary should sound natural and helpful, and include the following key details if available:
                                    Lead’s name
                                    Whether they are looking to buy or sell
                                    Desired location(s)
                                    Budget or price range
                                    Timeline or urgency
                                    Specific preferences (e.g. number of bedrooms, property type, etc.)
                                    After the summary, ask the agent:
                                    Would it be okay if I connected the call with them now?
                                    Example Output Format:
                                        Hi [Agent's Name], it’s Alex from your AI assistant. I just spoke with [Lead's Name]. They’re looking to [buy/sell] a home in [location], ideally within the [budget] range. They mentioned they’re hoping to move [timeline], and they’re looking for [specific preferences]. Would it be okay if I connected the call with them now?
                        The current person who is in call is real human agent and the conversations is about the user who wants to connect with you. This is the summary of conversation with the user.
                        input: {pre_summary}""


                        Ask the caller:
                                    Would you like to connect this call to a user now?
                        If the caller confirms a transfer/connect/talk/discuss/meet with the user, respond with:
                            "Transferring Message: Thanks for holding. You’re now connected. I’ll step away so you can take it from here."
                        If the caller declines, doesn’t want to connect or transfer, or is busy, respond with:
                            "Alright, the call will not be transferred. Let me know if you need anything else."
                                """
                
                
                greetings_from_ai = await self.ai_service.run_chat_without_tools([
                    {
                        "role" :"system",
                        "content" : f"""You are an extraction engine.\n\n
                                        You will always receive, in this order:\n
                                        • (optional) FIRST_NAME: <name>      ← line may be missing or value may be blank
                                        Task:\n
                                        1. Identify which message to return:\n
                                            • If the requested tag exists, return exactly or simmilar the text inside that tag.\n
                                            • Otherwise, return every line after the headers (FIRST_NAME) unchanged.\n
                                        2. Handle the <first_name> token
                                            • If a non‑empty FIRST_NAME was provided, replace every occurrence of
                                                <first_name> (case‑sensitive) with that name.
                                            • If FIRST_NAME is missing or empty, delete every occurrence of
                                                <first_name> and then:
                                                – collapse any resulting double spaces,
                                                – remove a space that appears immediately before a comma or period,
                                                – trim leading/trailing spaces.
                                        4. Output only the final text—no quotes, no extra whitespace,
                                        no commentary.
                                        Get the lead name from this summary and fill the <lead_name> from tehe text or return "lead": {pre_summary}
                                        """
                    },
                    {
                        "role" : "user",
                        "content" : f"""FIRST_NAME:  \n\n Hi <first_name>, I just spoke with <lead_name> and waiting to connect with you. Would you like to have a short breifing or connect this call to a user now?
                        """
                    }
                ])
        
                self.agents[call_id]['greetings'] = greetings_from_ai
                greetings = self.agents[call_id]['greetings']
        else:
            result = await self.gather_contact_info(call_id, greetings, self.agents[call_id]['direction'])

            self.agents[call_id]['fullname'] = result['fullname']
            self.agents[call_id]['greetings'] = result['greetings']
            self.agents[call_id]['email'] = result['email']
            self.agents[call_id]['phone'] = result['phone']
            self.agents[call_id]['description'] = result['description']
            self.agents[call_id]['existing_appointment'] = result['existing_appointment']
            self.agents[call_id]['address'] = result['address']

            fullname =self.agents[call_id]['fullname']
            greetings = self.agents[call_id]['greetings']
            email = self.agents[call_id]['email']
            phone = self.agents[call_id]['phone']
            description =self.agents[call_id]['description']
            existing_appointment =self.agents[call_id]['existing_appointment']

        if init_service is True:
            await self.initialize_services(call_id)
           

        # self.agents[call_id]["VAD"] =  VoiceActivityDetector(on_start=self.create_on_user_speech_handler(call_id))



        current_time = datetime.utcnow()
        print(f"Current UTC time: {current_time.isoformat()}")
        
        # Get user's timezone and show current time in user's timezone
        user_timezone = self.agents[call_id].get('timezone', 'UTC')
        print(f"User timezone: {user_timezone}")
        
        # Clean up the existing appointment string - remove duplicates and format nicely
        if existing_appointment:
            
            # Split by comma, strip whitespace, and remove duplicates while preserving order
            existing_appointment = sort_and_group_appointments(existing_appointment)
            if existing_appointment:
                appointments = []
                seen = set()
                for apt in existing_appointment.split(','):
                    apt = apt.strip()
                    if apt and apt not in seen:
                        appointments.append(apt)
                        seen.add(apt)

            existing_appointment = ', '.join(appointments) if appointments else None
        isAllowMeetingConflict = self.agents[call_id]['allowMeetingConflict']
        print("isAllowMeetingConflict: ", isAllowMeetingConflict)

        await self.ai_service.process_initial_message(call_id, self.get_agent_knowledge, greetings)
        
        if fullname is not None and fullname != "":
            # self.ai_service.add_message(call_id, "user", f"My Name is: {fullname}", "temp")
            self.ai_service.add_system_message(call_id, "system", f"Don't forget. This is the Name of the user you will use in this conversation: {fullname}")
        if email is not None and email != "":
            # self.ai_service.add_message(call_id, "user", f"My Email Address is: {email}", "temp")
            self.ai_service.add_system_message(call_id, "system", f"Don't forget. This is the email address of the user you will use in this conversation : {email}.")
        if phone is not None and phone != "":
            # self.ai_service.add_message(call_id, "user", f"My Phone Number is: {phone}", "temp")
            self.ai_service.add_system_message(call_id, "system", f"Don't forget. This is the Phone Number of the user you will use in this conversation: {phone}")
        else:
            self.ai_service.add_system_message(call_id, "system", f"This is the Phone Number of the user you will use in this conversation and you can ask the user if he/she wants to change the phone number: {self.format_us_phone(self.agents[call_id]['leadbound'])}")
        if description is not None and description != "":
            self.ai_service.add_system_message(call_id, "system", f"In Previous conversations with you this was the summary and you can use this info in this phone call: {description}")
       
            if not isAllowMeetingConflict and existing_appointment is not None and existing_appointment != "":
             print("Existing appointment found: ", existing_appointment)
            # user_timezone = self.agents[call_id].get('timezone', 'UTC')
            self.ai_service.add_system_message(
            call_id,
            "system",
            f"""Task: Help user schedule a 30-minute appointment/meeting.

            IMPORTANT SCHEDULING RULES:
            1. All meetings are exactly 30 minutes long
            2. Meetings can start at any 30-minute interval (e.g., 10:00am, 10:30am, 11:00am, 11:30am, etc.)
            3. A slot is available if there's no overlap with existing appointments

            BOOKED TIME SLOTS: {existing_appointment}

            INSTRUCTIONS:
            - If user requests a time that does NOT conflict with booked slots, proceed with scheduling
            - ONLY when user requests a time that CONFLICTS with booked slots:
              * Inform them the requested time is unavailable
              * Suggest 2-3 nearby available 30-minute slots on the same date
              * Look for gaps between appointments (e.g., if 11:00am-11:30am is booked but 11:30am-12:00pm is free, suggest 11:30am-12:00pm)
              * If no slots available on requested date, suggest alternative dates

            Do not proactively list available times unless there's a scheduling conflict.
            """
        )

        self.agents[call_id]['user_speaking'] = False
        self.agents[call_id]['ai_speaking'] = False
        self.agents[call_id]['websocket'] = None
        self.agents[call_id]['stream_sid'] = None
        

        return True
    
    async def initialize_services(self, call_id):
        if self.agents[call_id]['STT']['name'] == 'Deepgram':
            self.agents[call_id]["transcribe_service"] = self.initialize_transcriber(call_id, DeepgramService)
            # self.agents[call_id]["synthesis_service"] = self.agents[call_id]["transcribe_service"]
        elif self.agents[call_id]['STT']['name'] == 'AssemblyAI':
            self.agents[call_id]["transcribe_service"] = self.initialize_transcriber(call_id, TranscribeService)
            # self.agents[call_id]["synthesis_service"] = self.initialize_transcriber(stream_sid, DeepgramService)
        else :
            self.agents[call_id]["transcribe_service"] = self.initialize_transcriber(call_id, DeepgramService)
            

        if self.agents[call_id]['TTS']['name'] == 'Deepgram':
            if self.agents[call_id]['STT']['name'] == 'Deepgram' and self.agents[call_id]["transcribe_service"]:
                self.agents[call_id]["synthesis_service"] = self.agents[call_id]["transcribe_service"]
            else :
                self.agents[call_id]["synthesis_service"] = self.initialize_transcriber(call_id, DeepgramService)

        elif self.agents[call_id]['TTS']['name'] == 'Elevenlabs':
            self.agents[call_id]["synthesis_service"] = ElevenLabsService(self.loop)
        elif self.agents[call_id]['TTS']['name'] == 'Microsoft Azure':
            self.agents[call_id]["synthesis_service"] = AzureService(self.loop)
        elif self.agents[call_id]['TTS']['name'] == 'PlayHT':
            self.agents[call_id]["synthesis_service"] = PlayHT(self.loop)
        elif self.agents[call_id]['TTS']['name'] == 'Claude':
            self.agents[call_id]["synthesis_service"] = MurfAI(self.loop)
        elif self.agents[call_id]['TTS']['name'] == 'Pipertts':
            self.agents[call_id]["synthesis_service"] = PiperService(self.loop)
        else:
            self.agents[call_id]["synthesis_service"] = self.initialize_transcriber(call_id, DeepgramService)

        await self.agents[call_id]['synthesis_service'].update_call_id(call_id, self.queue_audio)
        
    async def handle_call(self, call_id: str, data):
        print("Handling call...", data)
        if data['direction'] != 'outbound-api':
            await self.update_agent_data(call_id, data)
            self.additionalinfo[call_id] = {
                "agent_id" : self.agents[call_id]['id'],
                "route_call" : False,
                "call_id": call_id,
                "agent_call_in_queue" : False   
            }
            self.agents[call_id]['call_sid'] = call_id
            response = self.twilio_service.initialize_call(call_id)
            return response
        else:
            if data['to'] not in self.calls:
                await self.update_details(None, None, data['to'], data['from'], data['pre_call_sid'])
            u_call_id = self.calls[data['to']]
            if data['pre_call_sid']:
                await self.initialize_services(u_call_id)
            self.additionalinfo[call_id] = {
                "agent_id" : self.agents[u_call_id]['id'],
                "route_call" : False,
                "call_id": u_call_id,
                "agent_call_in_queue" : False
            }
            del self.calls[data['to']]
            self.agents[u_call_id]['call_sid'] = call_id
            response = self.twilio_service.initialize_call(u_call_id)

            return response

    

    async def make_outgoing_call(self, phone_number: str):
        call_sid = self.twilio_service.make_call(phone_number)
        return call_sid

    async def process_all_info(self, stream_sid, call_id):
        print(f"Stream SID: {stream_sid}, Call SID: {call_id}")
        print("stt: ",self.agents[call_id]['STT']['name'])
        # if self.agents[call_sid]['STT']['name'] == 'Deepgram':
        #     await self.sessions[stream_sid]['transcribe_service'].establish_dg_connection(self.agents[call_sid]['STT']['model'])
        # else: self.sessions[stream_sid]['transcribe_service'].connect()
        # print("tts: ",self.agents[call_sid]['TTS']['name'])
        
        # # if self.agents[call_sid]['TTS']['name'] == 'Elevenlabs':
        # #     await self.sessions[stream_sid]['synthesis_service'].establish_connection( self.agents[call_sid]['TTS']['voice']['model'], self.agents[call_sid]['TTS']['model'])
        # if self.agents[call_sid]['TTS']['name'] == 'Deepgram':
        #     await self.sessions[stream_sid]['synthesis_service'].establish_sp_connection(self.agents[call_sid]['TTS']['voice']['model'])
        # elif self.agents[call_sid]['TTS']['name'] == 'Microsoft Azure':
        #     await self.sessions[stream_sid]['synthesis_service'].establish_connection(self.agents[call_sid]['TTS']['voice']['model'], stream_sid, self.queue_audio)
        #     # await self.sessions[stream_sid]['synthesis_service'].establish_connection(self.agents[call_sid]['TTS']['voice']['model'])
        # # self.sessions[call_sid]['stream_sid'] = stream_sid
        # elif self.agents[call_sid]['TTS']['name'] == 'PlayHT':
        #     await self.sessions[stream_sid]['synthesis_service'].establish_connection( self.agents[call_sid]['TTS']['voice']['model'], self.agents[call_sid]['TTS']['model'], stream_sid, self.queue_audio)
        
        if self.agents[call_id]['TTS']['name'] == 'Deepgram':
            await self.agents[call_id]['synthesis_service'].establish_sp_connection(self.agents[call_id]['TTS']['voice']['model'])

        elif self.agents[call_id]['TTS']['name'] == 'Elevenlabs':
            await self.agents[call_id]['synthesis_service'].establish_connection(self.agents[call_id]['TTS']['voice'], self.agents[call_id]['TTS']['model'])
        elif self.agents[call_id]['TTS']['name'] == 'Microsoft Azure':
            await self.agents[call_id]['synthesis_service'].establish_connection(self.agents[call_id]['TTS']['voice']['model'])
        elif self.agents[call_id]['TTS']['name'] == 'PlayHT':
            await self.agents[call_id]['synthesis_service'].establish_connection( self.agents[call_id]['TTS']['voice']['model'], self.agents[call_id]['TTS']['model'])
        elif self.agents[call_id]['TTS']['name'] == 'Claude':
            await self.agents[call_id]['synthesis_service'].establish_connection(self.agents[call_id]['TTS']['voice']['model'], self.agents[call_id]['TTS']['model'])
        elif self.agents[call_id]['TTS']['name'] == 'Pipertts':
            await self.agents[call_id]['synthesis_service'].establish_connection(self.agents[call_id]['TTS']['voice']['model'], self.agents[call_id]['TTS']['model'])
        else:
            await self.agents[call_id]['synthesis_service'].establish_sp_connection(self.agents[call_id]['TTS']['voice']['model'])

        greetings = self.agents[call_id]['greetings']


        if self.agents[call_id]['STT']['name'] == 'Deepgram':
            await self.agents[call_id]['transcribe_service'].establish_dg_connection(self.agents[call_id]['STT']['model'])
            # self.agents[call_id]["synthesis_service"] = self.agents[call_id]["transcribe_service"]
        elif self.agents[call_id]['STT']['name'] == 'AssemblyAI':
            self.agents[call_id]['transcribe_service'].connect()
            # self.agents[call_id]["synthesis_service"] = self.initialize_transcriber(stream_sid, DeepgramService)
        else :
            await self.agents[call_id]['transcribe_service'].establish_dg_connection(self.agents[call_id]['STT']['model'])

            # self.agents[call_id]["synthesis_service"] = self.agents[call_id]["transcribe_service"]
        await self.agents[call_id]['transcribe_service'].update_call_id(call_id, self.queue_audio)
        
        print("Done initializing session info")
        self.agents[call_id]['transmit_task'] = asyncio.create_task(self.transmit_after_delay(greetings, call_id))

        if (self.agents[call_id]['isAvailable'] == False):
            await self.synthesize_response('Currenty we are not available, Please contact us in our available time', call_id, None, True)
            # Schedule the call to end after 2 seconds
            self.clear_timer(call_id)
            self.timer[call_id] = Timer(5, self.twilio_service.hangup_call, args=[self.agents[call_id]['call_sid']])
            self.timer[call_id].start()
            return

        # await self.synthesize_response("This call may be monitored or recorded for quality and training purposes." , stream_sid)
        # # if self.agents[call_sid]['tts']['name'] == 'Deepgram':
        # await self.sessions[stream_sid]['synthesis_service'].flush_sp_ws()
        # greetings = self.agents[call_sid]['greetings']
        # result = await self.gather_contact_info(call_sid, greetings)

        

        #         fullname = result['fullname']
        # greetings = result['greetings']
        # email = result['email']
        # phone = result['phone']
        # description = result['description']
        # existing_appointment = result['existing_appointment']
        # Debug: Print current datetime for reference

        # updaedata= {
        #     "stream_sid" : stream_sid,
        #     "call_sid" : call_sid
        # }
        # await self.backend_service.update_call_info(updaedata)

    async def transmit_after_delay(self, greetings, call_id):
        await asyncio.sleep(4)  # Wait for speech
        print("Transmitting after delay...")
        estamitate_result = await estimate_speech_duration(greetings, 180)
        self.agents[call_id]['last_user_audio_time'] = time.time() + (estamitate_result['total_seconds'])
        self.ai_service.add_message(call_id, "assistant", greetings)
        self.ai_service.add_system_message(call_id, "assistant", greetings)
        await self.synthesize_response(greetings , call_id, None, True)
        # if self.agents[call_sid]['tts']['name'] == 'Deepgram':
        await self.agents[call_id]['synthesis_service'].flush_sp_ws()

    async def establish_tts(self,response, call_id):

        if call_id in self.additionalinfo and 'call_id' in self.additionalinfo[call_id]:
            if self.additionalinfo[call_id]['call_id'] in self.agents and self.agents[self.additionalinfo[call_id]['call_id']]['synthesis_service'].check_ws_connection() is None:
                await self.agents[self.additionalinfo[call_id]['call_id']]['synthesis_service'].establish_connection(self.agents[self.additionalinfo[call_id]['call_id']]['TTS']['voice'], self.agents[self.additionalinfo[call_id]['call_id']]['TTS']['model'])
            self.ai_service.add_message(self.additionalinfo[call_id]['call_id'], "assistant", response)
            self.ai_service.add_system_message(self.additionalinfo[call_id]['call_id'], "assistant", response)
            if self.additionalinfo[call_id]['call_id'] in self.agents:
                await self.synthesize_response(response, self.additionalinfo[call_id]['call_id'], None, True)
                await self.agents[self.additionalinfo[call_id]['call_id']]['synthesis_service'].flush_sp_ws()

    async def handle_stream_callback(self, data):
        """Handle the stream callback to get the streamSid."""
        stream_sid = data.get("StreamSid")
        call_sid = data.get("CallSid")
        return "OK", 200
    
    async def modify_greeting(self, name, greetings, call_sid, call_direction):
        direction = call_direction
        if direction == "outbound-api":
            direction = "outbound"
            
        # Use the new fields from the backend if available
        handle_call_type = self.agents[call_sid].get('handleCallType', 'INBOUND')
        actual_call_direction = self.agents[call_sid].get('callDirection', direction)
        address = self.agents[call_sid].get('address', None)
        city = ''
        if address is not None and 'city' in address and address['city'] != '':
            city = address['city']

        
        # Use the actual call direction from backend for better accuracy
        final_direction = actual_call_direction if actual_call_direction else direction
        
        greetings_from_ai = await self.ai_service.run_chat_without_tools([
            {
                "role" :"system",
                "content" : f"""You are an extraction engine.\n\n
                                You will always receive, in this order:\n
                                • DIRECTION: <inbound|outbound>\n
                                • (optional) FIRST_NAME: <name>      ← line may be missing or value may be blank
                                • (optional) CITY: <city>      ← line may be missing or value may be blank
                                • Then a text block that may or may not contain\n
                                <inbound_message> … </inbound_message> and\n
                                <outbound_message> … </outbound_message> tags.\n\n

                                Task:\n
                                1. Identify which message to return:\n
                                    • If the requested tag exists, return exactly the text inside that tag.\n
                                    • Otherwise, return every line after the headers (DIRECTION/FIRST_NAME/CITY) unchanged.\n
                                2. Handle the <first_name> token
                                    • If a non‑empty FIRST_NAME was provided, replace every occurrence of
                                        <first_name> (case‑sensitive) with that name.
                                    • If FIRST_NAME is missing or empty, delete every occurrence of
                                        <first_name> and then:
                                        – collapse any resulting double spaces,
                                        – remove a space that appears immediately before a comma or period,
                                        – trim leading/trailing spaces.
                                3. Handle the <city> token
                                    • If a non‑empty CITY was provided, replace every occurrence of
                                        <city> (case‑sensitive) with that name.
                                    • If CITY is missing or empty, delete every occurrence of
                                        <city> and then:
                                        – collapse any resulting double spaces,
                                        – remove a space that appears immediately before a comma or period,
                                        – trim leading/trailing spaces.
                                4. Output only the final text—no quotes, no extra whitespace,
                                no commentary.
                                """
            },
            {
                "role" : "user",
                "content" : f"""DIRECTION: {final_direction}\n FIRST_NAME: {name} \n CITY: {city}\n\n{greetings}"""
            }
        ])
        if greetings_from_ai:
            greetings = greetings_from_ai
                
        return greetings
    
    def process_audio_for_twilio(self, playht_audio_chunk_pcm):
   # 1. Load the WAV audio segment
        audio_segment = AudioSegment.from_wav(io.BytesIO(playht_audio_chunk_pcm)) # Use io.BytesIO for in-memory bytes

        # 2. Convert to 8kHz, mono, and then to mulaw (pydub handles intermediate PCM)
        # Ensure it's mono if not already, as mulaw is typically mono for telephony
        audio_segment = audio_segment.set_frame_rate(8000).set_channels(1)

        # 3. Export to raw mulaw bytes
        # pydub's 'raw' export assumes PCM unless you specify 'codec' for mulaw
        # For mulaw, you might need to export to a temporary file or use raw PCM and audioop.lin2ulaw
        # Simpler with pydub:
        mulaw_audio_bytes = audioop.lin2ulaw(audio_segment, 2)


        return mulaw_audio_bytes
    
    async def gather_contact_info(self, call_sid, greetings, call_direction):
        fullname = ""
        email = None
        phoneNumber = None
        description = None
        address= None
        existing_appointment = None
        crmUserId = None
        isBoom = self.agents[call_sid]['isBoom']

        if isBoom is not None or isBoom == True or isBoom == 'true':
            result = await self.backend_service.get_lead_info_boom({"phone" : self.agents[call_sid]['leadbound'] })
            if result and 'data' in result and result['data'] is not None:
                details = result['data']
                fullname = details['firstName']
                email = details['email']
                phoneNumber = details['phone']
                description = details['notes']
                crmUserId = details['id']
                self.agents[call_sid]['new_knowledge'] = True
        elif self.agents[call_sid]['integrations']['salesforce_connection_id']:

            formatted_number = self.formatToSalesforceNumber(self.agents[call_sid]['leadbound'])
            result = await self.ai_service.salesforce_service.get_lead_by_phone(self.agents[call_sid]['integrations']['salesforce_connection_id'], formatted_number)
            
            if result and len(result) > 0:
                details = result[0]
                fullname = details['LastName']
                # if details['FirstName']:
                #     fullname = details['FirstName'] + ' ' + details['LastName']
                crmUserId = details['Id']
                email = details['Email']
                phoneNumber = details['Phone']
                description = details['Description']
                
                self.agents[call_sid]['new_knowledge'] = True

        elif self.agents[call_sid]['integrations']['hubspot_connection_id']:

            result = await self.ai_service.hubspot_service.get_contact_by_phone(self.agents[call_sid]['integrations']['hubspot_connection_id'], self.agents[call_sid]['leadbound'])
            
            if result and 'results' in result and len(result['results']) > 0:
                details = result['results'][0]['properties']
                fullname = details['firstname'] + ' ' + details['lastname']
                email = details['email']
                phoneNumber = details['phone']
                description = details['notes']
                crmUserId = result['results'][0]['id']
                
                self.agents[call_sid]['new_knowledge'] = True

        elif self.agents[call_sid]['integrations']['zoho_connection_id']:

            result = await self.ai_service.zoho_service.get_lead_by_phone(self.agents[call_sid]['integrations']['zoho_connection_id'], self.agents[call_sid]['leadbound'])
            
            if result and len(result) > 0:
                details = result[0]
                fullname = details['Last_Name']
                if details['First_Name'] and details['First_Name'] is not None:
                    fullname = details['First_Name']
                crmUserId = details['Id']
                email = details['Email']
                phoneNumber = details['Phone']
                description = details['Description']
                
                self.agents[call_sid]['new_knowledge'] = True

        elif self.agents[call_sid]['integrations']['cinc_connection_id']:
            try:
                # Get account_id from agent info
                account_id = self.agents[call_sid].get('account_id')
                if account_id:
                    if account_id in self.prefetched_details:

                        lead = self.prefetched_details[account_id]
                        lead_id = lead.get('id')
                        if lead_id:
                            try:
                                # Fetch lead details with notes for this lead
                                lead_details = await self.cinc_service.get_lead_details(
                                    account_id=account_id, 
                                    lead_id=lead_id, 
                                    connection_id=self.agents[call_sid]['integrations']['cinc_connection_id']
                                )
                                # Extract notes from lead details if available
                                lead['notes'] = lead_details.get('notes', [])
                            except Exception as e:
                                print(f"Failed to fetch notes for lead {lead_id}: {e}")
                                lead['notes'] = []
                        else:
                            lead['notes'] = []

                        result = [lead]
                        del self.prefetched_details[account_id]
                    else:
                        result = await self.cinc_service.get_leads_by_phone(
                                account_id=account_id, 
                                phone=self.agents[call_sid]['leadbound'],
                                connection_id=self.agents[call_sid]['integrations']['cinc_connection_id']
                            )
                    print(f"DEBUG - CINC lead search result: {result}")
                    if result and len(result) > 0:
                        # Use the first matching lead
                        lead = result[0]
                        contact_info = lead.get('info', {}).get('contact', {})
                        routing_phone = lead.get('routing_phone', None)
                        if routing_phone is not None:
                            routing_phone =  self.format_us_number_simple(lead.get('routing_phone'))
                            self.agents[call_sid]['lead_routing_phone'] = routing_phone
                        print("Routing phone: ", self.agents[call_sid]['lead_routing_phone'])
                        # Extract contact information
                        first_name = contact_info.get('first_name', '')
                        last_name = contact_info.get('last_name', '')
                        
                        if first_name and last_name:
                            fullname = f"{first_name}"
                        elif first_name:
                            fullname = first_name
                        elif last_name:
                            fullname = last_name
                        
                        email = contact_info.get('email')
                        address = contact_info.get('mailing_address', {})
                        self.agents[call_sid]['address'] = address
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
                        
                        
                        self.agents[call_sid]['new_knowledge'] = True

                        print(f"DEBUG - Found CINC lead: {fullname}, Email: {email}, Phone: {phoneNumber}, Notes: {description}")

            except Exception as e:
                print(f"Error fetching CINC lead by phone {self.agents[call_sid]['leadbound']}: {e}")


        if self.agents[call_sid]['integrations'].get('calendly_connection_id'):
            # Check if there are any scheduled events for this user in Calendly

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
                            future_events = []
                            
                            # Get user's timezone
                            user_timezone = self.agents[call_sid].get('timezone', 'UTC')
                            print(f"Using user timezone for Calendly: {user_timezone}")
                            
                            for event in events_collection:
                                if 'start_time' in event:
                                    # Check if this is a future appointment using user's timezone
                                    is_future = (is_future_datetime(event['start_time'], user_timezone_str=user_timezone) and 
                                               event.get('status') != 'canceled')
                                    
                                    if is_future:
                                        # Check if end_time is available in Calendly event
                                        end_time = event.get('end_time', None)
                                        # Format time in user's timezone
                                        formatted_time = format_datetime_range_human_readable(
                                            event['start_time'], 
                                            end_time, 
                                            user_timezone_str=user_timezone
                                        )
                                        
                                        if formatted_time and formatted_time.strip():  # Ensure valid formatted time
                                            appointment_times.append(formatted_time)
                                            future_events.append({
                                                'name': event.get('name', 'Meeting'),
                                                'start': event['start_time'],
                                                'end': end_time,
                                                'formatted_time': formatted_time
                                            })
                            
                            if appointment_times:
                                # Remove duplicates while preserving order
                                unique_appointment_times = []
                                seen = set()
                                for time_str in appointment_times:
                                    if time_str not in seen:
                                        unique_appointment_times.append(time_str)
                                        seen.add(time_str)
                                
                                if existing_appointment:
                                    existing_appointment += ", " + ", ".join(unique_appointment_times)
                                else:
                                    existing_appointment = ", ".join(unique_appointment_times)
                            
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
     
                events_collection = []
                if events_result and 'records' in events_result:
                    events_collection = events_result['records']
                
                if events_collection and len(events_collection) > 0:
                    appointment_times = []
                    future_events = []
                    
                    # Get user's timezone
                    user_timezone = self.agents[call_sid].get('timezone', 'UTC')
                    # print(f"Using user timezone for Google Calendar: {user_timezone}")
                    
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
                        
                        # Check if this is a future appointment using user's timezone
                        is_future = (start_datetime and 
                                   is_future_datetime(start_datetime, user_timezone_str=user_timezone) and
                                   event.get('status') != 'cancelled')
                        
                        if is_future:
                            # Format time in user's timezone
                            formatted_time = format_datetime_range_human_readable(
                                start_datetime, 
                                end_datetime, 
                                user_timezone_str=user_timezone
                            )
                            if formatted_time and formatted_time.strip():  # Ensure valid formatted time
                                appointment_times.append(formatted_time)
                                future_events.append({
                                    'summary': event.get('summary', 'Meeting'),
                                    'start': start_datetime,
                                    'end': end_datetime,
                                    'formatted_time': formatted_time
                                })
                    
                    # Set existing_appointment with formatted times
                    if appointment_times:
                        # Remove duplicates while preserving order
                        unique_appointment_times = []
                        seen = set()
                        for time_str in appointment_times:
                            if time_str not in seen:
                                unique_appointment_times.append(time_str)
                                seen.add(time_str)
                        
                        if existing_appointment:
                            existing_appointment += ", " + ", ".join(unique_appointment_times)
                        else:
                            existing_appointment = ", ".join(unique_appointment_times)
                    
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

            try:
                events_result = await self.outlook_calendar_service.get_events(
                    self.agents[call_sid]['integrations']['outlook_connection_id']
                )
                # print("=== OUTLOOK CALENDAR EVENTS ===", json.dumps(events_result, indent=2))
                events_collection = []
                
                if events_result and 'records' in events_result:
                    events_collection = events_result['records']
                
                if events_collection and len(events_collection) > 0:
                    appointment_times = []
                    future_events = []
                    
                    # Get user's timezone
                    user_timezone = self.agents[call_sid].get('timezone', 'UTC')
                    
                    for event in events_collection:
                       
                        start_datetime = None
                        end_datetime = None
                        
                        if 'start' in event:
                            start = event['start'].get('dateTime', 'N/A')
                            timezone = event['start'].get('timeZone', 'N/A')
                            if start != 'N/A':
                                start_datetime = start
                            
                        if 'end' in event:
                            end = event['end'].get('dateTime', 'N/A')
                            timezone = event['end'].get('timeZone', 'N/A')
                            if end != 'N/A':
                                end_datetime = end
                        
                        # Check if this is a future appointment using user's timezone
                        is_future = start_datetime and is_future_datetime(start_datetime, user_timezone_str=user_timezone)
                        is_cancelled = event.get('isCancelled', False)
                        if start_datetime and is_future and not is_cancelled:
                            # Format time in user's timezone
                            formatted_time = format_datetime_range_human_readable(
                                start_datetime, 
                                end_datetime, 
                                user_timezone_str=user_timezone
                            )
                            if formatted_time and formatted_time.strip():  # Ensure valid formatted time
                                appointment_times.append(formatted_time)
                                future_events.append({
                                    'subject': event.get('subject', 'Meeting'),
                                    'start': start_datetime,
                                    'end': end_datetime,
                                    'formatted_time': formatted_time
                                })
                            else:
                                pass
                        else:
                            pass
                                           
                    if appointment_times:
                        # Remove duplicates while preserving order
                        unique_appointment_times = []
                        seen = set()
                        for time_str in appointment_times:
                            if time_str not in seen:
                                unique_appointment_times.append(time_str)
                                seen.add(time_str)
                        
                        if existing_appointment:
                            existing_appointment += ", " + ", ".join(unique_appointment_times)
                        else:
                            existing_appointment = ", ".join(unique_appointment_times)
                    
                else:
                    print("No upcoming Outlook Calendar events found.")

            except Exception as e:
                print(f"Error checking Outlook Calendar events: {str(e)}")
                print(traceback.format_exc())

        if crmUserId is not None:
            self.agents[call_sid]['lead_id'] = crmUserId
            self.agents[call_sid]['previous_convo_summary'] = description
        
        greetings = await self.modify_greeting(fullname, greetings, call_sid, call_direction)

        return {"greetings" : greetings ,
                "address":address,
                "email": email ,
                "phone": phoneNumber ,
                "description" : description,
                "fullname" : fullname,
                "existing_appointment": existing_appointment}
    
    async def enable_background_sound(self ,call_id, status = False):
        self.sessions[call_id]['background_sound'] = status
        if status is True:
            if not self.twilio_service.background_sound:
                audio_stream = await self.twilio_service.get_background_sound()
                self.twilio_service.background_sound = audio_stream
            await self.twilio_service.send_audio_stream(self.sessions[call_id]['websocket'], call_id, self.twilio_service.background_sound)

    async def complete_status_callback(self, data, pre_call_sid):
        """Handle the stream callback to get the streamSid."""

        call_sid = data.get("CallSid")
        call_duration = data.get("CallDuration")
        call_direction = data.get("Direction")
        call_status = data.get("CallStatus")
        time_stamp = data.get("Timestamp")
        resolution_status= 'RESOLVED'
        agent_id = None
        # self.sessions[call_sid]['stream_sid'] = stream_sid
    

        if self.additionalinfo and  call_sid in self.additionalinfo and "id" in self.additionalinfo[call_sid]:
            agent_id = self.additionalinfo[call_sid]['id']

        if self.additionalinfo and call_sid in self.additionalinfo and "route_call" in self.additionalinfo[call_sid] and self.additionalinfo[call_sid]['route_call'] == True:
            resolution_status = 'ROUTED'
        
        if self.additionalinfo and call_sid in self.additionalinfo and "call_id" in self.additionalinfo[call_sid]:
            call_sid = self.additionalinfo[call_sid]['call_id']

        if pre_call_sid is not None:
                try:
                    await self.establish_tts("The agent is busy right now. Will connect you later. Would you like to appointment instead?", pre_call_sid)
                except Exception as e:
                    print(f"Error in Establishing Agent TTS: {str(e)}")
                # self.agents[self.additionalinfo[pre_call_sid]['call_id']]['route_call'] = False

        data= {
            "duration" : call_duration,
            "direction": call_direction,
            "status": call_status,
            "call_sid" : call_sid,
            "agent_id" : agent_id,
            "timestamp" : time_stamp,
            "resolution_status": resolution_status
        }
        try:
            await self.backend_service.update_call_info(data)
        except Exception as e:
                print(f"Error Updating db on complete: {str(e)}")

        if call_status in ["failed", "busy", "no-answer", "canceled"]:
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
    
    async def fallback_status_callback(self, data, pre_call_sid=None):
        call_sid = data.get("CallSid")
        call_duration = data.get("CallDuration")
        call_direction = data.get("Direction")
        call_status = 'FAILED'
        time_stamp = data.get("Timestamp")
        resolution_status= 'FAILED'
        agent_id = None

        if self.agents and call_sid in self.agents and "id" in self.agents[call_sid]:
            agent_id = self.agents[call_sid]['id']

        if self.additionalinfo and call_sid in self.additionalinfo and "call_id" in self.additionalinfo[call_sid]:
            call_sid = self.additionalinfo[call_sid]['call_id']
            
        data= {
            "duration" : call_duration,
            "direction": call_direction,
            "status": call_status,
            "call_sid" : call_sid,
            "agent_id" : agent_id,
            "timestamp" : time_stamp,
            "resolution_status": resolution_status

        }
        if pre_call_sid is not None:
                try:
                    await self.establish_tts("The agent is busy right now. Will connect you later. Would you like to appointment instead?", pre_call_sid)
                except Exception as e:
                    print(f"Error on Establishing TTS on Fallback: {str(e)}")
                # self.agents[self.additionalinfo[pre_call_sid]['call_id']]['route_call'] = False

        self.twilio_service.client.calls(call_sid).update(status='completed')
        print(f"Call {call_sid} cleaned up.")

        try:
            await self.backend_service.update_call_info(data)
        except Exception as e:
                print(f"Error Updating db on complete: {str(e)}")
        
    async def get_nango_session_token(self, user_id, allowed_integrations=None):
        """Get a Nango session token for the frontend to use when connecting to third-party services
        
        Args:
            user_id: Unique identifier for the user
            allowed_integrations: List of integration IDs the user is allowed to connect to (optional) 
           
        """
        return await self.ai_service.get_nango_session_token(user_id, allowed_integrations)
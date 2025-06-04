import base64
from sqlalchemy.orm import Session
from app.services.playht_service import PlayHT
from app.services.twilio_service import TwilioService
from app.services.chatgpt_service import ChatGPTService
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
from datetime import datetime
from docx import Document
from PyPDF2 import PdfReader
from fastapi import UploadFile, WebSocketDisconnect
import wave
from app.config import settings
from pydub import AudioSegment
from threading import Timer
import numpy as np
import audioop
import os
import asyncio
import random
from io import BytesIO
import numpy as np
import soundfile as sf
import time , re
import traceback
from app.utils.responseformat import hubspot_patch_format
from app.utils.datetime_formatter import format_datetime_human_readable, format_datetime_range_human_readable, is_future_datetime
import json
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
        self.chatgpt_service = ChatGPTService()
        self.s3_service = S3Service()
        # self.playht_service = PlayHT()
        self.elevenlabs_service = ElevenLabsService()
        self.zoho_service = ZohoService()
        self.hubspot_service = HubSpotService()
        self.salesforce_service = SalesforceService()
        self.calendly_service = CalendlyService()
        self.google_calendar_service = GoogleCalendarService()
        self.outlook_calendar_service = OutlookCalendarService()
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
            "deepgram_transcribe_service": None,
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
                    # session['deepgram_transcribe_service'].establish_dg_connection()
                    # session['transcribe_service'].connect()

                if data['streamSid'] not in self.sessions or 'call_sid' not in self.sessions[data['streamSid']]:
                    continue

                # if (data['streamSid'] 
                # and self.sessions[data['streamSid']]['last_user_audio_time'] 
                # and time.time() - self.sessions[data['streamSid']]['last_user_audio_time'] > self.sessions[data['streamSid']]['wait_duration']):

                #     if data['streamSid'] and self.sessions[data['streamSid']]['wait_counter'] >= 2:
                #         self.sessions[data['streamSid']]['wait_counter'] = 0
                #         message = self.get_interrupt_message('end_call')
                #         self.chatgpt_service.add_message(data['streamSid'], "assistant", message)
                #         await self.synthesize_response(message, data['streamSid'])
                #         # Schedule the call to end after 2 seconds
                #         self.clear_timer()
                #         self.timer = Timer(5, self.twilio_service.hangup_call, args=[self.sessions[data['streamSid']]['call_sid']])
                #         self.timer.start()
                #         return
                    
                #     message = self.get_interrupt_message()
                #     self.chatgpt_service.add_message(data['streamSid'], "assistant", message)
                #     await self.synthesize_response(message, data['streamSid'])
                #     self.sessions[data['streamSid']]['wait_counter'] += 1

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
                    await session['deepgram_transcribe_service'].transcribe(audio_data)
                    # await session['transcribe_service'].transcribe(audio_data)

        except ConnectionClosedError as e:
            print(f"Connection closed with error: {e.code} - {e.reason}")
        except ConnectionClosedOK as e:
            print(f"Connection closed normally: {e.code} - {e.reason}")
        except Exception as e:
            print("Unexpected error:", e)
        finally:
            print("WebSocket connection closed.")
            session['deepgram_transcribe_service'].cancel_transmit()
            if session['stream_sid'] in self.chatgpt_service.conversations:
                conversations = self.chatgpt_service.conversations[session['stream_sid']]
                outputFile= f"recordings/{call_id}.wav"
                await self.convert_mulaw_to_wav(f"recordings/{call_id}.mulaw", outputFile)
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

                self.chatgpt_service.close_conversation(session['stream_sid'])
                self.twilio_service.remove_stream_from_queue(session['stream_sid'])
                del self.sessions[session['stream_sid']]
                self.agents[call_id]['websocket_closed'] = True
                # self.flush_agent(call_id)

            await session['deepgram_transcribe_service'].disconnect()
            # session['transcribe_service'].close()  # Close the transcriber service
            try:
                await websocket.close()
            except Exception as e:
                print("--Websocket connection Closed--")
    
    async def update_crm_data(self,call_id, lead_id: str, integrations, summary, appointment, prev_event_id, previous_convo_summary):
        event = appointment['eventData']

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
                await self.chatgpt_service.hubspot_service.update_leads(integrations['hubspot_connection_id'], body)
            else:
                if summary['phone'] == '' :
                    summary['phone'] = self.format_us_number_simple(self.agents[call_id]['from'])
                summary = self.remove_empty_values(summary)
                body = {
                    'contact' : summary,
                    'note' : notes
                }
                await self.chatgpt_service.hubspot_service.store_leads(integrations['hubspot_connection_id'], body)
                

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
                        await self.chatgpt_service.salesforce_service.update_leads(integrations['salesforce_connection_id'], body)
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
                        await self.chatgpt_service.salesforce_service.store_leads(integrations['salesforce_connection_id'], summary)
            except Exception as e:
                print("Lead Creat or Update failed" , e)

            try:
                if event is not None and event != '':
                    new_appointment = appointment['newAppointment']
                    update_appointment = appointment['updateAppointment']
                    delete_appointment = appointment['deleteAppointment']
                    if prev_event_id is not None and prev_event_id != '':
                        if update_appointment:
                            body = {
                                'Id' : prev_event_id,
                                'event' : event
                            }
                            response = await self.chatgpt_service.salesforce_service.update_event(integrations['salesforce_connection_id'], body)
                        elif delete_appointment:
                            response = await self.chatgpt_service.salesforce_service.delete_event(integrations['salesforce_connection_id'], {"Id" : prev_event_id})
                    else:
                        response = await self.chatgpt_service.salesforce_service.create_event(integrations['salesforce_connection_id'], event)
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
                        await self.chatgpt_service.zoho_service.update_leads(integrations['zoho_connection_id'], body)
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
                        await self.chatgpt_service.zoho_service.store_leads(integrations['zoho_connection_id'], body)
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
            speak_model = self.agents[call_sid]['voice']['model']
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
        self.chatgpt_service.update_interrupt_status(call_id, True)
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
        self.chatgpt_service.update_interrupt_status(call_id, False)

        response = await self.chatgpt_service.generate_response(call_id, transcript, self.synthesize_response, self.sessions[call_id]['deepgram_transcribe_service'].flush_sp_ws)

        if 'End Call Message' in response or self.contains_any_word(transcript) or  self.contains_any_word(response):
            self.agents[self.sessions[call_id]['call_sid']]['end_call'] = True
            response = response.replace('End Call Message', '')
            # Schedule the call to end after 2 seconds
            # wait_time = self.sessions[call_id]['wait_duration']
            # if self.sessions[call_id]['last_transcript_time']:
            # wait_time = self.sessions[call_id]['wait_duration'] + self.sessions[call_id]['prev_wait_duration']
            wait_time = 23
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
            "gender" : self.agents[self.sessions[call_id]['call_sid']]['voice']['gender'],
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
        model = self.agents[self.sessions[call_id]['call_sid']]['voice']['model']
        # Select TTS provider based on environment variable
        tts_provider = settings.tts_provider.lower()
        if tts_provider == "deepgram":
            audio_stream = await session['deepgram_transcribe_service'].stream_text_to_speech(text, model, call_id, self.queue_audio)
        # elif tts_provider == "playht":
        #     audio_stream = await self.playht_service.stream_text_to_speech(text, call_id, self.queue_audio)
        elif tts_provider == "elevenlabs":
            audio_stream = await self.elevenlabs_service.stream_text_to_speech(text)
            await self.twilio_service.send_audio_stream(session['websocket'], call_id, audio_stream)
            await self.twilio_service.enqueue_audio(call_id, audio_stream, 'response_buffer')
            result = await self.is_silent_or_empty_mulaw_numpy(audio_stream)
            session['prev_wait_duration'] = session['prev_wait_duration'] + session['wait_duration']
            session['wait_duration'] = result['duration']

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
        if not ai_interupted:
            
            await self.twilio_service.send_audio_stream(session['websocket'], call_id, audio_stream)
            await self.twilio_service.enqueue_audio(call_id, audio_stream ,'response_buffer')
            result = await self.is_silent_or_empty_mulaw_numpy(audio_stream)
            session['prev_wait_duration'] = session['prev_wait_duration'] + session['wait_duration']
            session['wait_duration'] = result['duration']
        # else:
        #     self.sessions[call_id]['ai_interrupt'] = False

    def get_interrupt_message(self , type = 'check_availability'):
        arrayObj = {
            'interrupt': [
                "Go ahead",
                "Please, go ahead."
                "Yes, do continue."
                "Yes, please go on."
                "I'm listening, please."
                "Yes, please continue. "
                "Of course, go ahead."
                "Go ahead, I'm listening."
                "Okay, I'm listening."
                "Sure, please continue."
            ],
            'check_availability': [
                "Are you around?",
                "Still with me?",
                "You there?",
                "Did I lose you?",
                "Are you gone?",
                "Can you hear me?",
                "Are you still online?",
                "Just checking if you're still here.",
                "Are you still listening?",
                "Hello? Still there?"
            ],
            'end_call': [
                "I understand you might be tied up. Feel free to message me when you're available. Wishing you a great day!",
                "No worries if you're busy. Just reach out when you have a moment. Take care!",
                "You may be caught up with something. Ping me whenever you're free. Have a wonderful day!",
                "Totally fine if you're busy. Let's connect when you get a chance. Hope your day is going well!",
                "If you're occupied, that's okay. Reach out anytime you're free. Have an awesome day!",
                "I get that things can get hectic. Connect with me whenever you're free. Take it easy!",
                "It seems like you might be busy. Just drop a message when you’re free. Enjoy your day!",
                "All good if you’re swamped. Let’s talk whenever you have time. Wishing you a nice day!",
                "You might have your hands full. Reach out whenever it works for you. Hope your day’s great!",
                "Understandable if you're unavailable right now. Let's chat when you're free. Have a great one!"
                ]
        } 


        return random.choice(arrayObj[type])

    def initialize_session_info(self, stream_sid, call_sid):
        # Initialize a session for this specific call
        if stream_sid not in self.sessions:
            self.sessions[stream_sid]={
                "deepgram_transcribe_service": self.initialize_transcriber(call_sid, stream_sid, DeepgramService),
                "transcribe_service" : self.initialize_transcriber(call_sid, stream_sid, TranscribeService),
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
                "google_calendar_connection_id": None
        }
        self.agents[call_id]['lead_id'] = None
        if 'integrations' in api_response['data']:
            self.agents[call_id]['integrations'] = api_response['data']['integrations']

            
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
        await self.sessions[stream_sid]['deepgram_transcribe_service'].establish_dg_connection()

        # self.sessions[call_sid]['stream_sid'] = stream_sid
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
        await self.sessions[stream_sid]['deepgram_transcribe_service'].flush_sp_ws()
        await self.chatgpt_service.process_initial_message(stream_sid, self.get_agent_knowledge)
        self.chatgpt_service.add_message(stream_sid, "assistant", greetings)
        self.chatgpt_service.add_system_message(stream_sid, "assistant", greetings)

        if fullname is not None and fullname != "":
            self.chatgpt_service.add_message(stream_sid, "user", f"My Name is: {fullname}")
            self.chatgpt_service.add_system_message(stream_sid, "system", f"Don't forget. This is the Name of the user you will use in this conversation: {fullname}")
        if email is not None and email != "":
            self.chatgpt_service.add_message(stream_sid, "user", f"My Email Address is: {email}")
            self.chatgpt_service.add_system_message(stream_sid, "system", f"Don't forget. This is the email address of the user you will use in this conversation : {email}.")
        if phone is not None and phone != "":
            self.chatgpt_service.add_message(stream_sid, "user", f"My Phone Number is: {phone}")
            self.chatgpt_service.add_system_message(stream_sid, "system", f"Don't forget. This is the Phone Number of the user you will use in this conversation: {phone}")
        else:
            self.chatgpt_service.add_system_message(stream_sid, "system", f"This is the Phone Number of the user you will use in this conversation and you can ask the user if he/she wants to change the phone number: {self.format_us_phone(self.agents[call_sid]['from'])}")
        if description is not None and description != "":
            self.chatgpt_service.add_system_message(stream_sid, "system", f"In Previous conversations with you this was the summary and you can use this info in this phone call: {description}")
       
        if not isAllowMeetingConflict and existing_appointment is not None and existing_appointment != "":
            print("Existing appointment found: ", existing_appointment)
            self.chatgpt_service.add_system_message(
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
            result = await self.chatgpt_service.salesforce_service.get_lead_by_phone(self.agents[call_sid]['integrations']['salesforce_connection_id'], formatted_number)
            
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

            result = await self.chatgpt_service.hubspot_service.get_contact_by_phone(self.agents[call_sid]['integrations']['hubspot_connection_id'], self.agents[call_sid]['from'])
            
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

            result = await self.chatgpt_service.zoho_service.get_lead_by_phone(self.agents[call_sid]['integrations']['zoho_connection_id'], self.agents[call_sid]['from'])
            
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

    async def process_file(self, file: UploadFile):
        """
        Process the uploaded file based on its MIME type and content.

        Supports: TXT, DOC/DOCX, PDF
        """
        # Read the file content
        file_content = await file.read()

        # Process based on MIME type
        if file.content_type == "text/plain":
            # Process TXT file
            return file_content.decode("utf-8")

        elif file.content_type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
            # Process DOCX file
            from io import BytesIO
            doc = Document(BytesIO(file_content))
            return "\n".join([paragraph.text for paragraph in doc.paragraphs])

        elif file.content_type == "application/pdf":
            # Process PDF file
            from io import BytesIO
            pdf_reader = PdfReader(BytesIO(file_content))
            text = ""
            for page in pdf_reader.pages:
                text += page.extract_text()
            return text

        else:
            # Unsupported file type
            print("Unsupported file type. Please upload TXT, DOC/DOCX, or PDF files.")
            return None

    async def convert_mulaw_to_wav(self, mulaw_file, wav_file):
        # Define WAV file settings
        wav_fp = wave.open(wav_file, 'wb')
        wav_fp.setnchannels(1)  # Mono channel
        wav_fp.setsampwidth(2)  # 16-bit samples
        wav_fp.setframerate(8000)  # 8 kHz sampling rate

        # Read the μ-law file
        with open(mulaw_file, 'rb') as mulaw_fp:
            while True:
                chunk = mulaw_fp.read(1024)
                if not chunk:
                    break

                # Convert μ-law to linear PCM
                pcm_chunk = audioop.ulaw2lin(chunk, 2)

                # Write the PCM chunk to the WAV file
                wav_fp.writeframes(pcm_chunk)

        wav_fp.close()
        if os.path.exists(mulaw_file):
                os.remove(mulaw_file)
        else:
            print("The file does not exist")

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
        return await self.chatgpt_service.get_nango_session_token(user_id, allowed_integrations)
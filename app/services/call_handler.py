import base64
from sqlalchemy.orm import Session
from app.services.twilio_service import TwilioService
from app.services.chatgpt_service import ChatGPTService
from app.services.s3_service import S3Service
from app.services.backend_service import BackendHandler
from app.services.polly_service import PollyService
from app.services.deepgram_service import DeepgramService
from app.services.assembly_ai_transcribe_service import TranscribeService
from websockets.exceptions import ConnectionClosedError, ConnectionClosedOK
import logging
from datetime import datetime
from docx import Document
from PyPDF2 import PdfReader
from fastapi import UploadFile
import wave
from app.config import settings
from pydub import AudioSegment
from threading import Timer
import numpy as np
import audioop
import os
# Configure logginga
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
        # self.transcribe_service = TranscribeService(on_transcript=self.handle_transcript)
        self.sessions = {}
        self.agents = {}
        self.completed_sessions = {}

    def get_business_agent(self, call_id: str):
        """Retrieve specific AI agent/business logic based on the dialed number."""

        return self.agents[call_id]
    
    async def process_input(self, call_id, websocket):
        await websocket.accept()
        session = {
                "deepgram_transcribe_service": None,
                "transcribe_service": None,
                "ai_speaking": False,
                "stream_sid": None,
                "background_sound": None,
                "end_call": False,
        }

        output_file = f"recordings/{call_id}.mulaw"
        # Open μ-law raw file for writing
        with open(output_file, 'wb') as mulaw_fp:
            pass  # Placeholder to ensure the file is created
        # wav_file = wave.open(output_file, 'wb')
        # wav_file.setnchannels(1)  # Mono audio
        # wav_file.setsampwidth(2)  # 16-bit audio
        # wav_file.setframerate(8000)  # 8kHz sampling rate (default for Twilio)
        with open(output_file, "ab") as f:
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
                        session['transcribe_service'].connect()


                    if data["event"] == "media":
                        media = data["media"]
                        chunk = media["payload"]
                        chunk_bytes = base64.b64decode(chunk)
                        f.write(chunk_bytes)
                        await self.twilio_service.enqueue_audio(data['streamSid'], chunk_bytes ,'audio_buffer')

                    if data['streamSid'] and not self.twilio_service.is_empty(data['streamSid'], 'response_buffer'):
                        print("Processing response buffers...")
                        response_audio = await self.twilio_service.get_or_dequeue_audio(data['streamSid'], 'response_buffer')
                        # await self.twilio_service.send_control_command(session['websocket'], 'stop')
                        if self.sessions[data['streamSid']]['background_sound'] is True:
                            await self.stop_stream(data['streamSid'])
                        session['ai_speaking'] = True
                        f.write(response_audio)
                        await self.twilio_service.send_audio_stream(session['websocket'], data['streamSid'], response_audio)

                    if data['streamSid'] and not self.twilio_service.is_empty(data['streamSid'], 'audio_buffer'):
                        audio_data = await self.twilio_service.get_or_dequeue_audio(data['streamSid'], 'audio_buffer')
                        # await self.transcribe_service.transcribe(audio_data)
                        await session['transcribe_service'].transcribe(audio_data)

                        

            except ConnectionClosedError as e:
                print(f"Connection closed with error: {e.code} - {e.reason}")
            except ConnectionClosedOK as e:
                print(f"Connection closed normally: {e.code} - {e.reason}")
            except Exception as e:
                print("Unexpected error:", e)
            finally:
                print("WebSocket connection closed.")
                conversations = self.chatgpt_service.conversations[session['stream_sid']]
                agent_id = self.agents[call_id]['id']
                outputFile= f"recordings/{call_id}.wav"
                await self.convert_mulaw_to_wav(f"recordings/{call_id}.mulaw", outputFile)
                # os.remove(output_file)
                recordingUrl = await self.s3_service.uploadToS3(outputFile)

                data = {
                    "call_sid" : call_id,
                    "conversations": conversations,
                    "recording_url" : recordingUrl,
                    "agent_id" : agent_id
                }
                await self.backend_service.update_conversation_info(data)
                await websocket.close()
                self.transcribe_service.close()  # Close the transcriber service
        

                self.chatgpt_service.close_conversation(session['stream_sid'])
                self.twilio_service.remove_stream_from_queue(session['stream_sid'])
                session['deepgram_transcribe_service'].disconnect()

    def initialize_transcriber(self, call_id: str, Service : TranscribeService | DeepgramService):
        """Initialize transcriber with bound methods for handling transcripts and user speech."""
        return Service(
            on_transcript=self.create_on_transcript_handler(call_id),
            on_start=self.create_on_user_speech_handler(call_id),
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
        await self.twilio_service.stop_audio_stream(self.sessions[call_id]['websocket'], call_id)
        self.sessions[call_id]['background_sound'] = False

    async def on_user_speech(self, call_id):
        if self.sessions[call_id]['ai_speaking']:
            await self.stop_stream(call_id)
            self.sessions[call_id]['ai_speaking'] = False

    async def handle_transcript(self, transcript, call_id):
        print(f"Transcript: {transcript}")
        # await self.enable_background_sound(call_id, True)
        response = await self.chatgpt_service.generate_response(call_id, transcript, self.synthesize_response, self.get_agent_knowledge)
        if 'End Call Message:' in response:
            self.sessions[call_id]['end_call'] = True
            response = response.replace('End Call Message:', '')
            # Schedule the call to end after 2 seconds
            timer = Timer(10, self.twilio_service.hangup_call, args=[self.sessions[call_id]['call_sid']])
            timer.start()
            
        if 'Routing Message:' in response:
            self.sessions[call_id]['route_call'] = True
            response = response.replace('Routing Message:', '')
            # Schedule the call to end after 2 seconds
            timer = Timer(10, self.twilio_service.redirect_call, args=[self.sessions[call_id]['call_sid'] ,self.agents[self.sessions[call_id]['call_sid']]['routingInfo']['routingNumber']])
            timer.start()

        print(f"Response: {response}")
        await self.synthesize_response(response, call_id)

    async def get_agent_knowledge(self, call_id):
        return {        
            "knowledge" : self.agents[self.sessions[call_id]['call_sid']]['knowledge'],
            "routingInfo" : self.agents[self.sessions[call_id]['call_sid']]['routingInfo'],
        }

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
        if not session:
            return
        start_time = datetime.now()
        # audio_stream = await self.polly_service.stream_text_to_speech(chunk)
        model = self.agents[self.sessions[call_id]['call_sid']]['voice']['model']
        audio_stream = await session['deepgram_transcribe_service'].stream_text_to_speech(text, model)
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds() * 1000  # Calculate duration in milliseconds
        logging.info(f"Total Deepgram duration: {duration:.3f} ms")
        await self.twilio_service.enqueue_audio(call_id, audio_stream ,'response_buffer')

        print('audio streamed')

    def initialize_session_info(self, stream_sid, call_sid):
        # Initialize a session for this specific call
        if stream_sid not in self.sessions:
            self.sessions[stream_sid]={
                "deepgram_transcribe_service": self.initialize_transcriber(stream_sid, DeepgramService),
                "transcribe_service" : self.initialize_transcriber(stream_sid, TranscribeService),
                "ai_speaking": False,
                "stream_sid": stream_sid,
                "background_sound": None,
                "websocket" : None,
                "call_sid" : call_sid,
                "end_call" : False,
                "route_call" : False,
            }
        
    async def handle_call(self, call_id: str, data):
        print("Handling call...")
        api_response = await self.backend_service.create_call_info(data)
        self.agents[call_id] = api_response['data']['agent']
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
        # self.sessions[call_sid]['stream_sid'] = stream_sid
        data= {
            "stream_sid" : stream_sid,
            "call_sid" : call_sid
        }
        await self.backend_service.update_call_info(data)
        if (self.agents[call_sid]['isAvailable'] == False):
            await self.synthesize_response('Currenty we are not available, Please contact us in our available time', stream_sid)
            # Schedule the call to end after 2 seconds
            timer = Timer(5, self.twilio_service.hangup_call, args=[call_sid])
            timer.start()
            return

        greetings = self.agents[call_sid]['greetings']
        await self.synthesize_response(greetings, stream_sid)
        
        return "OK", 200
    
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
            raise ValueError("Unsupported file type. Please upload TXT, DOC/DOCX, or PDF files.")
        

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


        
    async def complete_status_callback(self, data):
        """Handle the stream callback to get the streamSid."""
        print(data)
        call_sid = data.get("CallSid")
        call_duration = data.get("CallDuration")
        call_direction = data.get("Direction")
        call_status = data.get("CallStatus")
        time_stamp = data.get("Timestamp")
        # self.sessions[call_sid]['stream_sid'] = stream_sid
        agent_id = self.agents[call_sid]['id']
        data= {
            "duration" : call_duration,
            "direction": call_direction,
            "status": call_status,
            "call_sid" : call_sid,
            "agent_id" : agent_id,
            "timestamp" : time_stamp,

        }
        await self.backend_service.update_call_info(data) 
        return "OK", 200




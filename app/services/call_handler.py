import base64
from sqlalchemy.orm import Session
from app.services.playht_service import PlayHT
from app.services.twilio_service import TwilioService
from app.services.chatgpt_service import ChatGPTService
# from app.services.chatgpt_service_v2 import ChatGPTService
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
import time
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
        self.playht_service = PlayHT()
        # self.transcribe_service = TranscribeService(on_transcript=self.handle_transcript)
        self.sessions = {}
        self.agents = {}
        self.completed_sessions = {}
        self.timer = None

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

            silence_threshold = 0.10  # Adjust as needed
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
            "wait_duration": 10,
            "stream_sid": None,
            "background_sound": None,
            "end_call": False,
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
                    session['deepgram_transcribe_service'].establish_dg_connection()
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
                    print("Processing response buffers...")
                    response_audio = await self.twilio_service.get_or_dequeue_audio(data['streamSid'], 'response_buffer')
                    # await self.twilio_service.send_control_command(session['websocket'], 'stop')
                    if self.sessions[data['streamSid']]['background_sound'] is True:
                        await self.stop_stream(data['streamSid'])
                    session['ai_speaking'] = True
                    with open(output_file, "ab") as f:
                        f.write(response_audio)
                    await self.twilio_service.send_audio_stream(session['websocket'], data['streamSid'], response_audio)

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
            if session['stream_sid'] in self.chatgpt_service.conversations:
                conversations = self.chatgpt_service.conversations[session['stream_sid']]
                outputFile= f"recordings/{call_id}.wav"
                await self.convert_mulaw_to_wav(f"recordings/{call_id}.mulaw", outputFile)
                # os.remove(output_file)
                recordingUrl = await self.s3_service.uploadToS3(outputFile)
                agent_id = self.agents[call_id]['id']
                data = {
                    "call_sid" : call_id,
                    "conversations": conversations,
                    "recording_url" : recordingUrl,
                    "agent_id" : agent_id
                }
                self.chatgpt_service.close_conversation(session['stream_sid'])
                self.twilio_service.remove_stream_from_queue(session['stream_sid'])
                del self.sessions[session['stream_sid']]

                try:
                    await self.backend_service.update_conversation_info(data)
                    isBoom = self.agents[call_id]['isBoom']
                    print(isBoom)
                    if isBoom is not None or isBoom == True or isBoom == 'true' or isBoom != 'false':
                        await self.backend_service.update_conversation_bh({"conversations": data['conversations'],})
                except Exception as e:
                    print(e)
                    
                self.agents[call_id]['websocket_closed'] = True
                # self.flush_agent(call_id)

            session['deepgram_transcribe_service'].disconnect()
            # session['transcribe_service'].close()  # Close the transcriber service
            try:
                await websocket.close()
            except Exception as e:
                print("--Websocket connection Closed--")

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
            self.sessions[call_id]['wait_duration'] = 10
            self.sessions[call_id]['ai_interrupt'] = False

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
        # await asyncio.sleep(1)  # Wait for 1 second
        # self.sessions[call_id]['ai_interrupt'] =  True
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

        response = await self.chatgpt_service.generate_response(call_id, transcript, self.synthesize_response)
        if 'End Call Message' in response or self.contains_any_word(transcript) or  self.contains_any_word(response):
            self.agents[self.sessions[call_id]['call_sid']]['end_call'] = True
            response = response.replace('End Call Message', '')
            # Schedule the call to end after 2 seconds
            self.clear_timer()
            self.timer = Timer(11, self.twilio_service.hangup_call, args=[self.sessions[call_id]['call_sid']])
            self.timer.start()
            
        if 'Routing Message' in response or 'I am forwarding the call' in response:
            response = response.replace('Routing Message', '')
            # Schedule the call to end after 2 seconds
            self.clear_timer()
            self.timer = Timer(11, self.twilio_service.redirect_call,
                          args=[
                            self.sessions[call_id]['call_sid'],
                            self.agents[self.sessions[call_id]['call_sid']]['routingInfo']['routingNumber'],
                            self.call_routed
                            ]
                        )
            self.timer.start()

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
        start_time = datetime.now()
        # audio_stream = await self.polly_service.stream_text_to_speech(chunk)
        model = self.agents[self.sessions[call_id]['call_sid']]['voice']['model']
        audio_stream = await session['deepgram_transcribe_service'].stream_text_to_speech(text, model)
        # audio_stream = await self.playht_service.stream_text_to_speech(text, call_id, self.queue_audio)

        result = await self.is_silent_or_empty_mulaw_numpy(audio_stream)
        session['wait_duration'] = result['duration'] + 3

        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds() * 1000  # Calculate duration in milliseconds
        logging.info(f"Total Deepgram duration: {duration:.3f} ms")
        await self.twilio_service.enqueue_audio(call_id, audio_stream ,'response_buffer')
        session['last_user_audio_time'] = time.time()
        print('audio streamed', session['last_user_audio_time'])

    async def queue_audio(self, call_id, audio_stream):
        await self.twilio_service.enqueue_audio(call_id, audio_stream ,'response_buffer')

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
                "deepgram_transcribe_service": self.initialize_transcriber(stream_sid, DeepgramService),
                "transcribe_service" : self.initialize_transcriber(stream_sid, TranscribeService),
                "ai_speaking": False,
                "ai_interrupt": False,
                "wait_counter": 0,
                "wait_duration": 10,
                "stream_sid": stream_sid,
                "background_sound": None,
                "websocket" : None,
                "call_sid" : call_sid,
                "last_user_audio_time" : None
            }
        
    async def handle_call(self, call_id: str, data):
        print("Handling call...")
        api_response = await self.backend_service.create_call_info(data)
        self.agents[call_id] = api_response['data']['agent']
        self.agents[call_id]['isBoom'] = data['isBoom']
        self.agents[call_id]['complete_call'] = False
        self.agents[call_id]['websocket_closed'] = False
        self.agents[call_id]['end_call'] = False
        self.agents[call_id]['route_call'] = False
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
            self.clear_timer()
            self.timer = Timer(5, self.twilio_service.hangup_call, args=[call_sid])
            self.timer.start()
            return

        greetings = self.agents[call_sid]['greetings']
        await self.synthesize_response(greetings , stream_sid)
        await self.chatgpt_service.process_initial_message(stream_sid, self.get_agent_knowledge)
        self.chatgpt_service.add_message(stream_sid, "assistant", greetings)
        self.chatgpt_service.add_system_message(stream_sid, "assistant", greetings)
        
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
        if self.agents[call_sid]['complete_call'] == True and self.agents[call_sid]['websocket_closed'] == True:
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
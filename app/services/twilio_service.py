# app/services/twilio_service.py
import os, asyncio
from twilio.rest import Client
import base64  # Add this import
from app.config import settings
from twilio.twiml.voice_response import VoiceResponse, Gather, Connect , Record, Dial
import audioop
import wave
# # Path to your background sound file (WAV format)
ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
BACKGROUND_SOUND_FILE =os.path.abspath(os.path.join(ROOT_DIR, '../' , 'keyboard.wav'))
print(BACKGROUND_SOUND_FILE)


class TwilioService:
    def __init__(self):
        self.client = Client(settings.twilio_account_sid, settings.twilio_auth_token)
        self.audio_buffer = asyncio.Queue()
        self.response_buffer = asyncio.Queue()
        self.background_sound = None
        # A dictionary to dynamically store queues by their unique IDs
        self.queue_map = {}

    def get_or_create_queue(self, queue_id):
        """Get an existing queue or create a new one for the given queue_id."""
        if queue_id not in self.queue_map:
            self.queue_map[queue_id] =  {
                "response_buffer" : asyncio.Queue(),
                "audio_buffer" : asyncio.Queue()
            }
        return self.queue_map[queue_id]
    
    async def enqueue_audio(self, queue_id, value, type):
        """Produce an item and put it in the queue with the given ID."""
        queue = self.get_or_create_queue(queue_id)
        await queue[type].put(value)

    async def get_or_dequeue_audio(self, queue_id, type):
        """Consume an item from the queue with the given ID."""
        queue = self.get_or_create_queue(queue_id)
        value = await queue[type].get()
        queue[type].task_done()
        return value
    
    async def dequeue_all_except_next(self, queue_id, type):
        """Remove all queued items except the next one in the queue."""
        queue = self.get_or_create_queue(queue_id)[type]

        # Get the size of the queue
        queue_size = queue.qsize()

        # If there are more than one items, remove all but the next one
        if queue_size > 1:
            temp_queue = asyncio.Queue()

            # Keep the last item
            for _ in range(queue_size - 1):
                await queue.get()
                queue.task_done()
            
            # Transfer the last item to a temporary queue
            last_item = await queue.get()
            queue.task_done()
            await temp_queue.put(last_item)

            # Replace the queue with the temporary queue
            self.queue_map[queue_id][type] = temp_queue
    
    def is_empty(self , queue_id , type):
        queue = self.get_or_create_queue(queue_id)
        return queue[type].empty()
    
     # Function to close a conversation
    def remove_stream_from_queue(self, queue_id):
        if queue_id in self.queue_map:
            del self.queue_map[queue_id]
            print(f"Queue ID {queue_id} is now closed.")
        else:
            print(f"Conversation ID {queue_id} does not exist.")

    def initialize_call(self, call_sid):
        """Initialize the call state with required fields."""
        print("Initializing call...")
        response = VoiceResponse()
        # response.record(recording_status_callback=f"{settings.base_url}/recording_status_callback")
        # response.say("This call may be monitored or recorded for quality assurance and training purposes.")
        connect = Connect()
        connect.stream(
            url=f"wss://{settings.domain}/audio-stream/{call_sid}",
            status_callback=f"{settings.base_url}/stream_callback",
            status_callback_method="POST",
        )
        
        print("Call initialized.")
        response.append(connect)

        return response
        
    # Helper function to read the WAV file and loop it
    async def get_background_sound(self):
        def read_and_convert():
            with wave.open(BACKGROUND_SOUND_FILE, "rb") as infile:
                frames = infile.readframes(infile.getnframes())
                # Convert to mu-law encoding
                mu_law_data = audioop.lin2ulaw(frames, infile.getsampwidth())
            return mu_law_data
        mu_law_data = await asyncio.to_thread(read_and_convert)
        return mu_law_data
    
    async def generate_voice_response(self, text: str):
        response = VoiceResponse()
        response.say(text, voice="alice", language="en-US")
        gather = Gather(input="speech", action=f"/gather", method="POST", timeout=5, speechTimeout="auto")
        response.append(gather)
        return response
    
    async def stop_audio_stream(self, websocket, stream_sid):
        print("Stopping audio stream...")
        await websocket.send_json({
            "event": "clear",
            "streamSid": stream_sid
        })

    async def send_audio_stream(self, websocket, stream_sid, audio_data):
        """Send audio stream as a websocket media event to Twilio."""
        # print("Sending audio stream...")
        # Encode audio data to base64 and remove filetype header
        encoded_audio_data = base64.b64encode(audio_data).decode('utf-8')
        await websocket.send_json({
            "event": "media",
            "streamSid": stream_sid,
            "media": {
                "payload": encoded_audio_data
            }
        })

    def hangup_call(self, call_sid):
        response = VoiceResponse()
        # response.say("Thank you. We have gathered all required information. Goodbye!", voice="alice", language="en-US")
        response.hangup()
        self.client.calls(call_sid).update(status="completed")

    def make_call(self, to: str):
        call = self.client.calls.create(
            to=to,
            from_=settings.twilio_phone_number,
            url=f"{settings.base_url}/incoming_call"  # Replace with your actual URL
        )
        return call.sid
    
    # Function to redirect an ongoing call
    def redirect_call(self, call_sid, new_number, call_routed):
        try:
            # Update the ongoing call to forward it
            # call = self.client.calls(call_sid).update(
            #     method='POST',
            #     url=f"{settings.ai_backend_url}/call/forward-call?newNumber={new_number}&callerId={callerId}"
            # )
            call = self.client.calls(call_sid).update(
                twiml=f"""
                <Response>
                    <Dial callerId="{new_number}">{new_number}</Dial>
                </Response>
                """
            )
            call_routed(call_sid)
            print(f"Call redirected to {new_number}, Status: {call.status}")
        except Exception as e:
            print(f"Error redirecting call: {e}")

    def wait_caller(self):
        """Wait for the caller to respond."""
        response = VoiceResponse()
        response.say("Please hold while I connect you.")
        response.play(url=f"https://cdn-boomershub.s3.amazonaws.com/assets/media/ringMusic.mp3", loop=99 )
        return response

    
    def update_call(self, call_sid, conference_name):
        hold_twiml_url = f"{settings.base_url}/ai-transfer?conference_name={conference_name}"  # Endpoint that serves the TwiML with the hold message
        call = self.client.calls(call_sid).update(
            url=hold_twiml_url,
            method="POST"
        )
        return call
    
    def ai_transfer(self, conference_name):
        """
        This is triggered when AI decides user wants a real human.
        Holds the user in a conference with hold music/ringtone.
        """
        print("Transferring call to conference:", conference_name)
        response = VoiceResponse()
        dial = Dial()
        dial.conference(
            conference_name,
            # wait_url=f"{settings.base_url}/hold-user-twiml",
            start_conference_on_enter=True,
            end_conference_on_exit=True
        )
        response.append(dial)
        return response

    def call_agent(self, call_sid, twilio_number, agent_number):
        """
        AI uses this to call the real agent and ask if they want to join.
        Params: agent_number, conference_name
        """
        call = self.client.calls.create(
            to=agent_number,
            from_=twilio_number,
            url=f"{settings.base_url}/incoming_call?call_sid={call_sid}",
            status_callback=f"{settings.base_url}/complete_status_callback?call_sid={call_sid}",
            fallback_url=f"{settings.base_url}/fallback_status_callback?call_sid={call_sid}",
        )
        return {"status": "Calling agent", "agent_call_sid": call.sid}


    def ask_agent(self, call_sid, summary):
        """
        When agent answers, ask them if they want to talk to user.
        Press 1 to join the call.
        """
        response = VoiceResponse()
        gather = Gather(
            num_digits=1,
            action=f"/agent-response?call_sid={call_sid}",
            timeout=50
        )
        gather.say(summary + "You have a user waiting. Press 1 to join the call.")
        response.append(gather)
        # response.say("No input received. Goodbye.")
        # response.hangup()
        return response


    async def agent_response(self, digits ,call_sid):
        """Handle agent keypress response"""

        response = VoiceResponse()
        if digits == "1":
            # Connect agent to the same conference
            self.update_call(call_sid)
            print("Transferring call to conference:", f"conf_{call_sid}")
            conference_name = f"conf_{call_sid}"
            dial = Dial()
            dial.conference(
                conference_name,
                start_conference_on_enter=True
            )
            response.append(dial)

        else:
            response.say("You chose not to join. Goodbye.")
            response.hangup()
        return response



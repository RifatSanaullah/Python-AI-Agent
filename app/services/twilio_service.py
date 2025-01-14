# app/services/twilio_service.py
import os, asyncio
from twilio.rest import Client
import base64  # Add this import
from app.config import settings
from twilio.twiml.voice_response import VoiceResponse, Gather, Connect , Record
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
        self.active_calls = {}
        self.fields_needed = {
            "name": None,
            "email": None,
            "phone_number": None,
        }
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
        if (call_sid not in self.active_calls):
            self.active_calls[call_sid] = {
                "fields_needed": self.fields_needed.copy(),
                "is_complete": False
            }
            response = VoiceResponse()
            # response.record(recording_status_callback=f"{settings.base_url}/recording_status_callback")
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
        print("Sending audio stream...")
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
    def redirect_call(self, call_sid, new_number, callerId):
        try:
            # Update the ongoing call to forward it
            call = self.client.calls(call_sid).update(
                method='POST',
                url=f"{settings.ai_backend_url}/call/forward-call?newNumber={new_number}&callerId={callerId}"
            )
            print(f"Call redirected to {new_number}, Status: {call.status}")
        except Exception as e:
            print(f"Error redirecting call: {e}")


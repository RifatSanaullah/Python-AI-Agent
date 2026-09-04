import assemblyai as aai
import asyncio

class TranscribeService:
    def __init__(self,loop=None, speak_model=None):
        self.api_key = ""
        aai.settings.api_key = self.api_key
        self.on_transcript = None  # Store the callback function
        self.transcriber = None
        self.on_start = None
        self.call_id = None

    async def update_call_id(self, call_id, queue_audio=None):
        self.call_id = call_id

    def connect(self, on_transcript=None, on_start=None):
        self.on_transcript = on_transcript  # Assign the callback function
        self.on_start = on_start  # Assign the callback function
        self.transcriber = aai.RealtimeTranscriber(
            sample_rate=8000, 
            encoding=aai.AudioEncoding.pcm_mulaw,
            end_utterance_silence_threshold=1800,
            on_data=self.on_data,
            on_error=self.on_error,
            on_open=self.on_open,
            on_close=self.on_close
        )
        self.transcriber.connect()

    async def disconnect(self):
        if self.transcriber:
            self.transcriber.close()
            self.transcriber = None

    async def transcribe(self, audio_chunk: bytes):
        self.transcriber.stream(audio_chunk)
    
    def on_open(self, session_opened: aai.RealtimeSessionOpened):
        "Called when the connection has been established."
        print("Session ID:", session_opened.session_id)


    def on_data(self,transcript: aai.RealtimeTranscript):
        "Called when a new transcript has been received."
        if not transcript.text:
            return
        asyncio.run(self.on_start(self.call_id))  # Call the on_start callback if provided
        if isinstance(transcript, aai.RealtimeFinalTranscript):
            print(transcript.text, end="\r\n")
            if self.on_transcript:
                asyncio.run(self.on_transcript(transcript.text, self.call_id))
        else:
            print(transcript.text, end="\r")



    def on_error(self, error: aai.RealtimeError):
        "Called when the connection has been closed."
        print("An error occured:", error)


    def on_close(self):
        "Called when the connection has been closed."
        print("Closing Session")

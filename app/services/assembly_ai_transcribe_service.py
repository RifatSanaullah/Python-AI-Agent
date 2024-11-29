import assemblyai as aai
import asyncio  # Import asyncio

class TranscribeService:
    def __init__(self, on_transcript=None):
        self.api_key = "9576f4ea99e14b90a1c6ee4100b4536f"
        aai.settings.api_key = self.api_key
        self.on_transcript = on_transcript  # Store the callback function
        self.transcriber = aai.RealtimeTranscriber(
            sample_rate=8000, 
            encoding=aai.AudioEncoding.pcm_mulaw,
            on_data=self.on_data,
            on_error=self.on_error,
            on_open=self.on_open,
            on_close=self.on_close
        )
        self.transcriber.connect()  
              
    def connect(self):
        self.transcriber.connect()

    def close(self):
        self.transcriber.close()

    async def transcribe(self, audio_chunk: bytes):
        self.transcriber.stream(audio_chunk)
    
    def on_open(self, session_opened: aai.RealtimeSessionOpened):
        "Called when the connection has been established."
        print("Session ID:", session_opened.session_id)


    def on_data(self,transcript: aai.RealtimeTranscript):
        "Called when a new transcript has been received."
        if not transcript.text:
            return

        if isinstance(transcript, aai.RealtimeFinalTranscript):
            print(transcript.text, end="\r\n")
            if self.on_transcript:
                asyncio.run(self.on_transcript(transcript.text))
        else:
            print(transcript.text, end="\r")



    def on_error(self, error: aai.RealtimeError):
        "Called when the connection has been closed."
        print("An error occured:", error)


    def on_close(self):
        "Called when the connection has been closed."
        print("Closing Session")

import asyncio
from deepgram.utils import verboselogs

from deepgram import (
    DeepgramClient,
    SpeakOptions,
    LiveTranscriptionEvents,
    LiveOptions,
    DeepgramClientOptions
)
from app.config import settings


class DeepgramService:
    def __init__(self , on_transcript = None ,on_start=None):
        self.config = DeepgramClientOptions(
            options={"keepalive": "true"} # Comment this out to see the effect of not using keepalive
        )
        self.deepgram = DeepgramClient(settings.deepgram_apikey, self.config)

        self.transcribeQueue = None
        self.emptySentence = 0

        self.on_transcript = on_transcript
        self.on_start = on_start
        self.speaker = self.deepgram.speak.rest.v("1")
        # connect to websocket
        self.transcribeOptions = LiveOptions(
            model="nova-2",
            encoding='mulaw', 
            sample_rate=8000,
            smart_format=True,
            # vad_events=True,
            utterance_end_ms="1000",
            interim_results=True,
            endpointing=1200
            # Time in milliseconds of silence to wait for before finalizing speech
            )

        self.dg_connection = None
        # self.lock_exit = threading.Lock()
        # self.exit = False

    async def stream_text_to_speech(self, text: str , model = "aura-asteria-en"):
        try:
            options = SpeakOptions(
                model= model,
                encoding='mulaw',
                sample_rate=8000,
                container="none"
            )
            response = self.speaker.stream({"text": text}, options)
            return response.stream.getbuffer()

        except Exception as e:
            print(f"An error occurred: {e}")
            raise


    def establish_dg_connection(self):
        print("Establishing Deepgram Connection....")
        if self.dg_connection:
            self.dg_connection.finish()
        self.dg_connection = self.deepgram.listen.websocket.v("1")
        self.dg_connection.on(LiveTranscriptionEvents.Open, self.on_open)

        self.dg_connection.start(options=self.transcribeOptions)
        self.dg_connection.keep_alive()



    async def transcribe(self, audio_chunk: bytes):
        self.dg_connection.send(audio_chunk)

    
    def on_open(self, open, val):
        "Called when the connection has been established."
        print("Session ID:", open)
        self.dg_connection.on(LiveTranscriptionEvents.Transcript, self.on_data)
        # self.dg_connection.on(LiveTranscriptionEvents.SpeechStarted, self.on_started)
        self.dg_connection.on(LiveTranscriptionEvents.Close, self.on_close)
        self.dg_connection.on(LiveTranscriptionEvents.Error, self.on_error)


    def on_data(self,res,**kwargs):
        "Called when a new transcript has been received."
        result = kwargs['result']
        is_final = result.is_final
        sentence = result.channel.alternatives[0].transcript
        if sentence and is_final : 
            print('Final' , sentence)
            if self.on_transcript:
                asyncio.run(self.on_transcript(sentence))
        
        
        elif sentence and not is_final : 
            asyncio.run(self.on_start())



    def on_started(self, message, **kwargs):
        # asyncio.run(self.on_update(True))
        print(message)
        
        
    def on_error(self, error, message, **kwargs):
        "Called when the connection has been closed."
        print('error: ' , error)



    def on_close(self, close,message, **kwargs):
        "Called when the connection has been closed."
        print("Closing Session", kwargs)
    
    def disconnect(self):
        self.dg_connection.finish()
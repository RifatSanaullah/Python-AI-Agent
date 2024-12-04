import os ,asyncio
from deepgram.utils import verboselogs

from deepgram import (
    DeepgramClient,
    SpeakOptions,
    LiveTranscriptionEvents,
    LiveOptions,
)


class DeepgramService:
    def __init__(self ,on_transcript = None ,on_update=None):
        self.deepgram = DeepgramClient('3ebb3fc8a4d20c9929cb4760848b3d95a23fd123')
        self.options = SpeakOptions(
            model="aura-asteria-en",
            encoding='mulaw',
            sample_rate=8000,
            container="none"
        )

        self.on_transcript = on_transcript
        self.on_update = on_update
        self.speaker = self.deepgram.speak.rest.v("1")
        # connect to websocket
        self.transcribeOptions = LiveOptions(
            model="nova-2-conversationalai",
            encoding='mulaw', 
            sample_rate=8000,
            smart_format=True,
            no_delay=True,
            # vad_events=True,
            # Time in milliseconds of silence to wait for before finalizing speech
            endpointing=1000
            )

        self.dg_connection = None
        # self.lock_exit = threading.Lock()
        # self.exit = False

    async def stream_text_to_speech(self, text: str):
        try:
            response = self.speaker.stream({"text": text}, self.options)
            return response.stream.getbuffer()

        except Exception as e:
            print(f"An error occurred: {e}")
            raise


    def establishDGConnection(self):
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
        # print(kwargs.result)

        result = kwargs['result']
        sentence = result.channel.alternatives[0].transcript
        print(sentence)
        if not sentence:
            return
            
        if self.on_transcript:
            asyncio.run(self.on_transcript(sentence))



    def on_started(self, message, **kwargs):
        # asyncio.run(self.on_update(True))
        print(message)
        
        
    def on_error(self, error, message, **kwargs):
        "Called when the connection has been closed."
        print('error: ' , error)



    def on_close(self, close,message, **kwargs):
        "Called when the connection has been closed."
        print("Closing Session", kwargs)
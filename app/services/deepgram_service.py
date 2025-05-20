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
import threading
import re
class DeepgramService:
    def __init__(self , on_transcript = None ,on_start=None ,loop =None):
        self.config = DeepgramClientOptions(
            options={"keepalive": "true"} # Comment this out to see the effect of not using keepalive
        )
        self.deepgram = DeepgramClient(settings.deepgram_apikey, self.config)

        self.transcribeQueue = None
        self.emptySentence = 0

        self.on_transcript = on_transcript
        self.on_start = on_start
        self.speaker = self.deepgram.speak.rest.v("1")
        self.complete_sentence = ''
        self.transmit_task = None
        self.loop = loop or asyncio.get_event_loop()
        # self.lock = threading.Lock()
        # connect to websocket
        self.transcribeOptions = LiveOptions(
            model="nova-3",
            encoding='mulaw',
            sample_rate=8000,
            smart_format=True,
            # vad_events=True,
            utterance_end_ms="1000",
            interim_results=True,
            endpointing=700,
            # Time in milliseconds of silence to wait for before finalizing speech
            )

        self.dg_connection = None
        # self.lock_exit = threading.Lock()
        # self.exit = False

    def is_sentence_complete(self, sentence):
        return bool(re.search(r'[.!?]$', sentence.strip()))

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

    async def transmit_after_delay(self):
        try:
            if self.is_sentence_complete(self.complete_sentence):
                await asyncio.sleep(1.2)  # Wait for more speech
            else:
                await asyncio.sleep(2.2)  # Wait for more speech

            # with self.lock:
            if self.on_transcript and self.complete_sentence.strip():
                await self.on_transcript(self.complete_sentence.strip())
                self.complete_sentence = ''
            self.transmit_task = None
        except asyncio.CancelledError:
            # Canceled because more speech came in
            pass

    def on_data(self,res,**kwargs):
        "Called when a new transcript has been received."
        result = kwargs['result']
        is_final = result.is_final
        sentence = result.channel.alternatives[0].transcript
        if sentence and is_final and sentence.strip():
            print("sentence: ", sentence)
            self.complete_sentence += ' ' + sentence.strip()
            # with self.lock:

            # Schedule new task: wait 2 seconds, then emit final transcript
            self.cancel_transmit()
            self.transmit_task = asyncio.run_coroutine_threadsafe(
                self.transmit_after_delay(),
                self.loop
            )
            print('Final' , self.complete_sentence)
        
        
        elif sentence and not is_final: 
            # Cancel previous delayed task
            self.cancel_transmit()
            asyncio.run(self.on_start())

    def cancel_transmit(self):
        if self.transmit_task:
            self.transmit_task.cancel()

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
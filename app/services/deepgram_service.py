import asyncio
from deepgram.utils import verboselogs

from deepgram import (
    DeepgramClient,
    LiveTranscriptionEvents,
    LiveOptions,
    DeepgramClientOptions,
    SpeakWebSocketEvents,
    SpeakWSOptions,
)

from app.config import settings
import threading
import re
class DeepgramService:
    def __init__(self , on_transcript = None,on_start=None ,loop =None, speak_model = "aura-2-thalia-en"):
        self.config = DeepgramClientOptions(
            options={"keepalive": "true"} # Comment this out to see the effect of not using keepalive
        )
        self.deepgram = DeepgramClient(settings.deepgram_apikey, self.config)

        self.transcribeQueue = None
        self.emptySentence = 0

        self.on_transcript = on_transcript
        self.on_start = on_start
        # self.speaker = self.deepgram.speak.rest.v("1")
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
        self.speakOptions = SpeakWSOptions(
                model= speak_model,
                encoding='mulaw',
                sample_rate=8000,
            )
        self._exit = threading.Event()
        self.dg_connection = None
        self.sp_dg_connection = None
        self.queue_audio = {}
        # self.lock_exit = threading.Lock()
        # self.exit = False
        
    def is_sentence_complete(self, sentence):
        return bool(re.search(r'[.!?]$', sentence.strip()))

    async def stream_text_to_speech(self, text: str , model, call_id, queue_audio):
        try:
            # options = SpeakOptions(
            #     model= model,
            #     encoding='mulaw',
            #     sample_rate=8000,
            #     container="none"
            # )
            # response = self.speaker.stream({"text": text}, options)
            # return response.stream.getbuffer()
            self.queue_audio = {
                'call_id': call_id,
                "queue_audio": queue_audio
            }
            await self.sp_dg_connection.send_text(text)
            # self._socket.send(json.dumps({"type": "Speak", "text": text}))
        except Exception as e:
            print(f"An error occurred: {e}")
            raise


    async def establish_dg_connection(self , model = "nova-3"):
        print("Establishing Deepgram Connection....")
        if self.dg_connection:
            await self.dg_connection.finish()
        if self.sp_dg_connection:
            await self.sp_dg_connection.finish()
        self.dg_connection = self.deepgram.listen.asyncwebsocket.v("1")
        self.dg_connection.on(LiveTranscriptionEvents.Open, self.on_open)
        self.transcribeOptions['model'] = model
        await self.dg_connection.start(options=self.transcribeOptions)
        await self.dg_connection.keep_alive()

        self.sp_dg_connection = self.deepgram.speak.asyncwebsocket.v("1")
        self.sp_dg_connection.on(SpeakWebSocketEvents.Open, self.on_sp_open)

        if await self.sp_dg_connection.start(self.speakOptions) is False:
            print("Failed to start connection")
            return

    async def transcribe(self, audio_chunk: bytes):
        await self.dg_connection.send(audio_chunk)

    async def on_sp_open(self, open, val):
        "Called when the connection has been established."
        print("Speak Session ID:", open)
        self.sp_dg_connection.on(SpeakWebSocketEvents.AudioData, self.on_binary_data)
        self.sp_dg_connection.on(SpeakWebSocketEvents.Close, self.on_sp_close)
        self.sp_dg_connection.on(SpeakWebSocketEvents.Error, self.on_sp_error)

        # Start the receiver thread for audio data

    async def on_sp_close(self, message, **kwargs):
        "Called when the connection has been closed."
        print("Closing Speak Session", kwargs)

    async def on_sp_error(self, message, **kwargs):
        "Called when the connection has been error."
        print("Closing Speak Session", kwargs)

    async def on_binary_data(self, res , **kwargs):
            data = kwargs.get('data')
            await self.queue_audio['queue_audio'](self.queue_audio['call_id'],data)
            # Process the binary data as needed
            
    async def flush_sp_ws(self):
        "Flush the current audio stream."
        if self.sp_dg_connection:
            await self.sp_dg_connection.flush()
        return
    
    async def on_open(self, open, val):
        "Called when the connection has been established."
        print("Session ID:", open)
        self.dg_connection.on(LiveTranscriptionEvents.Transcript, self.on_data)
        # self.dg_connection.on(LiveTranscriptionEvents.SpeechStarted, self.on_started)
        self.dg_connection.on(LiveTranscriptionEvents.Close, self.on_close)
        self.dg_connection.on(LiveTranscriptionEvents.Error, self.on_error)

    async def transmit_after_delay(self):
        try:
            if self.is_sentence_complete(self.complete_sentence):
                await asyncio.sleep(0.6)  # Wait for more speech
            else:
                await asyncio.sleep(1)  # Wait for more speech

            # with self.lock:
            if self.on_transcript and self.complete_sentence.strip():
                await self.on_transcript(self.complete_sentence.strip())
                self.complete_sentence = ''
            self.transmit_task = None
        except asyncio.CancelledError:
            # Canceled because more speech came in
            pass

    async def on_data(self,res,**kwargs):
        "Called when a new transcript has been received."
        result = kwargs['result']
        is_final = result.is_final
        sentence = result.channel.alternatives[0].transcript
        if sentence:
            self.cancel_transmit()
            await self.on_start()
            if is_final and sentence.strip():
                print("sentence: ", sentence)
                self.complete_sentence += ' ' + sentence.strip()
                # with self.lock:

                # Schedule new task: wait 2 seconds, then emit final transcript
                self.transmit_task = asyncio.run_coroutine_threadsafe(
                    self.transmit_after_delay(),
                    self.loop
                )
                print('Final' , self.complete_sentence)


    def cancel_transmit(self):
        if self.transmit_task:
            self.transmit_task.cancel()

    async def on_started(self, message, **kwargs):
        # asyncio.run(self.on_update(True))
        print(message)
        
        
    async def on_error(self, message, **kwargs):
        "Called when the connection has been closed."
        print('error: ' , message)



    async def on_close(self, message, **kwargs):
        "Called when the connection has been closed."
        print("Closing Session", kwargs)
    
    async def disconnect(self):
        await self.dg_connection.finish()
        await self.sp_dg_connection.finish()
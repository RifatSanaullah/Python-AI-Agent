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
from app.utils.honeybadger_utils import notify_honeybadger
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
        self.same_sentence = 0
        self.prev_sentence = ""
        self.skip_final = False
        # self.lock = threading.Lock()
        # connect to websocket
        self.transcribeOptions = LiveOptions(
            model="nova-3",
            encoding='mulaw',
            sample_rate=8000,
            # smart_format=True,
            # vad_events=True,
            utterance_end_ms="1000",
            interim_results=True,
            endpointing=400,  # Much shorter silence detection
            filler_words=False,  # Can help with speed
            # Time in milliseconds of silence to wait for before finalizing speech
            )
        self.speakOptions = SpeakWSOptions(
                model= speak_model,
                encoding='mulaw',
                sample_rate=8000,
            )
        # self._exit = threading.Event()
        self.dg_connection = None
        self.sp_dg_connection = None
        self.queue_audio = {}
        # self.lock_exit = threading.Lock()
        # self.exit = False
        
    def _notify_hb(self, error_or_message, extra_context=None):
        context = {
            "component": "DeepgramService",
            "call_id": self.queue_audio.get("call_id") if isinstance(self.queue_audio, dict) else None,
        }
        if extra_context:
            context.update(extra_context)
        notify_honeybadger(error_or_message, context)

    def is_sentence_complete(self, sentence):
        return bool(re.search(r'[.!?]$', sentence.strip()))
    
    async def send_stream_to_tts(self, text):
        await self.sp_dg_connection.send_text(text)

    async def stream_text_to_speech(self, text: str):
        try:
            # options = SpeakOptions(
            #     model= model,
            #     encoding='mulaw',
            #     sample_rate=8000,
            #     container="none"
            # )
            # response = self.speaker.stream({"text": text}, options)
            # return response.stream.getbuffer()

            await self.send_stream_to_tts(text)
            # self._socket.send(json.dumps({"type": "Speak", "text": text}))
        except Exception as e:
            print(f"An error occurred: {e}")
            self._notify_hb(e, {"operation": "stream_text_to_speech", "text_preview": (text[:80] if isinstance(text, str) else None)})
            raise
    
    async def update_call_id(self, call_id, queue_audio=None):

        self.queue_audio = {
                'call_id': call_id,
                "queue_audio": queue_audio
            }


    async def establish_dg_connection(self, model = "nova-3"):
        print("Establishing Deepgram Connection....")
        try:
            if self.dg_connection:
                await self.dg_connection.finish()
            self.dg_connection = self.deepgram.listen.asyncwebsocket.v("1")
            self.dg_connection.on(LiveTranscriptionEvents.Open, self.on_open)
            self.transcribeOptions['model'] = model
            await self.dg_connection.start(options=self.transcribeOptions)
            await self.dg_connection.keep_alive()
        except Exception as e:
            self._notify_hb(e, {"operation": "establish_dg_connection", "model": model})
            raise

    async def establish_sp_connection(self, model = "aura-2-thalia-en"):
        print("Establishing Speak Connection....")
        try:
            if self.sp_dg_connection:
                await self.sp_dg_connection.finish()
            self.speakOptions['model'] = model
            self.sp_dg_connection = self.deepgram.speak.asyncwebsocket.v("1")
            self.sp_dg_connection.on(SpeakWebSocketEvents.Open, self.on_sp_open)

            if await self.sp_dg_connection.start(self.speakOptions) is False:
                print("Failed to start connection")
                self._notify_hb("Deepgram Speak start failed", {"operation": "establish_sp_connection", "model": model})
                return
        except Exception as e:
            self._notify_hb(e, {"operation": "establish_sp_connection", "model": model})
            raise

    async def transcribe(self, audio_chunk: bytes):
        try:
            await self.dg_connection.send(audio_chunk)
        except Exception as e:
            self._notify_hb(e, {"operation": "transcribe_send", "audio_chunk_len": len(audio_chunk) if audio_chunk else 0})
            raise

    async def on_sp_open(self, open, val):
        "Called when the connection has been established."
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
        self._notify_hb("Deepgram Speak error", {"event": "on_sp_error", "message": str(message), "details": kwargs})

    async def on_binary_data(self, res , **kwargs):
            data = kwargs.get('data')
            try:
                await self.queue_audio['queue_audio'](self.queue_audio['call_id'],data)
            except Exception as e:
                self._notify_hb(e, {"operation": "on_binary_data", "data_len": len(data) if data else 0})
                raise
            # Process the binary data as needed
            
    async def flush_sp_ws(self):
        "Flush the current audio stream."
        if self.sp_dg_connection:
            await self.sp_dg_connection.flush()
        return
    
    async def on_open(self, open, val):
        "Called when the connection has been established."
        self.dg_connection.on(LiveTranscriptionEvents.Transcript, self.on_data)
        # self.dg_connection.on(LiveTranscriptionEvents.SpeechStarted, self.on_started)
        self.dg_connection.on(LiveTranscriptionEvents.Close, self.on_close)
        self.dg_connection.on(LiveTranscriptionEvents.Error, self.on_error)

    async def transmit_after_delay(self):
        try:
            if self.is_sentence_complete(self.complete_sentence):
                await asyncio.sleep(0.6)  # Wait for more speech
            else:
                await asyncio.sleep(0.6)  # Wait for more speech
            # with self.lock:
            if self.on_transcript and self.complete_sentence.strip():
                sentence = self.complete_sentence
                self.complete_sentence = ''
                try:
                    await self.on_transcript(sentence.strip())
                except Exception as e:
                    self._notify_honeybadger(e, {"operation": "on_transcript_callback", "sentence_preview": sentence.strip()[:120]})
                    raise
            self.transmit_task = None
        except asyncio.CancelledError:
            # Canceled because more speech came in
            pass
        except Exception as e:
            # Unexpected error in delayed transmit
            self._notify_honeybadger(e, {"operation": "transmit_after_delay"})
            raise
            
    async def check_complete_sentence(self, sentence: str):
        if sentence.strip() == self.prev_sentence.strip():
            self.same_sentence += 1
            self.skip_final = False
            if self.same_sentence > 2:
                self.skip_final = True
        else:
            self.prev_sentence = sentence.strip()
            self.skip_final = False
        return self.skip_final


    async def on_data(self,res,**kwargs):
        "Called when a new transcript has been received."
        result = kwargs['result']
        is_final = result.is_final
        sentence = result.channel.alternatives[0].transcript
        if sentence:
            print("Transcript: ", sentence, "is_final: ", is_final)
            self.cancel_transmit()
            try:
                await self.on_start()
            except Exception as e:
                self._notify_honeybadger(e, {"operation": "on_start_callback"})
                # Continue handling; raising could break the stream
            if is_final and sentence.strip():
                self.same_sentence = 0
                self.complete_sentence += ' ' + sentence.strip()
                # with self.lock:

                # Schedule new task: wait 2 seconds, then emit final transcript
                try:
                    self.transmit_task = asyncio.run_coroutine_threadsafe(
                        self.transmit_after_delay(),
                        self.loop
                    )
                except Exception as e:
                    self._notify_honeybadger(e, {"operation": "schedule_transmit_after_delay"})
                    raise
                print('Final' , self.complete_sentence)


    def cancel_transmit(self):
         if self.transmit_task:
            self.transmit_task.cancel()
            self.transmit_task = None

    async def on_started(self, message, **kwargs):
        # asyncio.run(self.on_update(True))
        print("speech detected", message)
        
        
    async def on_error(self, message, **kwargs):
        "Called when the connection has been closed."
        print('error: ' , message)
        self._notify_hb("Deepgram Listen error", {"event": "on_error", "message": str(message), "details": kwargs})



    async def on_close(self, message, **kwargs):
        "Called when the connection has been closed."
        print("Closing Session", kwargs)
    
    async def disconnect(self):
        if self.dg_connection:
            await self.dg_connection.finish()
        if self.sp_dg_connection:
            await self.sp_dg_connection.finish()   
            
    def update_tts_interrupt(self):
        return
    
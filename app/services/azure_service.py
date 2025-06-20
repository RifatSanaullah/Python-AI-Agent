import azure.cognitiveservices.speech as speechsdk
from app.config import settings
import io, threading, asyncio
class AzureService:
    def __init__(self, voice: str = "en-US-AriaNeural"):
        self.speech_key = settings.azure_key
        self.region = settings.azure_region
        self.voice = voice
        self.queue_audio = {}
        self.speech_synthesizer = None
        self.tts_task = None
        self.tts_request = None
        self._receiver_thread = None
        # Initialize Azure Speech config
        self.speech_config = speechsdk.SpeechConfig(
            endpoint=f"wss://{settings.azure_region}.tts.speech.microsoft.com/cognitiveservices/websocket/v2",
            subscription=settings.azure_key
        )
        self._exit=None
        # self.speech_config = speechsdk.SpeechConfig(subscription=self.speech_key, region=self.region)
        self.speech_config.speech_synthesis_voice_name = self.voice
        self.speech_config.set_speech_synthesis_output_format(speechsdk.SpeechSynthesisOutputFormat.Raw8Khz8BitMonoMULaw)


    # async def establish_connection(self, voice:str):
    #     self.speech_config.speech_synthesis_voice_name = voice

    #     self.speech_synthesizer = speechsdk.SpeechSynthesizer(speech_config=self.speech_config, audio_config=None)


    # async def stream_text_to_speech(self, text: str, voice: str, call_id,  queue_audio=None):
    #     """
    #     Synthesizes text using Azure TTS and sends the 8kHz u-law audio
    #     Directly requests 8kHz u-law from Azure.
    #     """

    #     # Receives a text from console input and synthesizes it to result.
    #     # while True:
    #     print("Enter some text that you want to synthesize, Ctrl-Z to exit")
    #     result = self.speech_synthesizer.speak_text_async(text).get()
    #     # Check result
    #     if result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted:
    #         audio_data = result.audio_data
    #         await queue_audio(call_id, audio_data)
    #     elif result.reason == speechsdk.ResultReason.Canceled:
    #         cancellation_details = result.cancellation_details
    #         print("Speech synthesis canceled: {}".format(cancellation_details.reason))
    #         if cancellation_details.reason == speechsdk.CancellationReason.Error:
    #             print("Error details: {}".format(cancellation_details.error_details))
    #     return
    #     # Optional: Choose a voice. Neural voices generally sound better,
    #     # and Azure will handle the downsampling to 8kHz ULaw for you.

    # async def flush_sp_ws(self):
    #     return


    def start_synthesiser(self):
        self.tts_request = speechsdk.SpeechSynthesisRequest(input_type=speechsdk.SpeechSynthesisRequestInputType.TextStream)
        self.tts_task = self.speech_synthesizer.speak_async(self.tts_request)
        # self._receiver_thread = threading.Thread(target=asyncio.run, args=(self.receiver(),))
        # self._receiver_thread.start()
        # self._exit = threading.Event()
        print("Synthesiser Start")


    async def establish_connection(self, voice:str):
        self.speech_config.speech_synthesis_voice_name = voice

        self.speech_synthesizer = speechsdk.SpeechSynthesizer(speech_config=self.speech_config, audio_config=None)
        self.speech_synthesizer.synthesizing.connect(lambda evt: print("[audio]", end=""))

        self.start_synthesiser()
        # self._exit = threading.Event()
        print("Established Connection")

    async def receiver(self):

        try:
            while True:
                if self.tts_task is None or self._exit.is_set():
                    break
                await self.get_tts_data()
        except Exception as e:
            print(f"receiver: {e}")

    async def get_tts_data(self):
                result = self.tts_task.get()
                # Check result
                if result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted:
                    audio_data = result.audio_data
                    await self.queue_audio['queue_audio'](self.queue_audio['call_id'],audio_data)
                elif result.reason == speechsdk.ResultReason.Canceled:
                    cancellation_details = result.cancellation_details
                    print("Speech synthesis canceled: {}".format(cancellation_details.reason))
                    if cancellation_details.reason == speechsdk.CancellationReason.Error:
                        print("Error details: {}".format(cancellation_details.error_details))
                return

    async def stream_text_to_speech(self, text: str, voice: str, call_id,  queue_audio=None):

            if 'call_id' not in self.queue_audio:
                self.queue_audio = {
                    'call_id': call_id,
                    "queue_audio": queue_audio
                }

            return self.tts_request.input_stream.write(text)

    async def flush_sp_ws(self):
        print("FLUSH REQUEST")
        await self.disconnect()
        if self.tts_task:
                await self.get_tts_data()
                self.start_synthesiser()
        return
    async def disconnect(self):
        print("Disconnected")
        if self.tts_request is not None:
            self.tts_request.input_stream.close()
        # if self._exit is not None:
        #     self._exit.set()
        # if self._receiver_thread is not None:
        #     self._receiver_thread.join()
        #     self._receiver_thread=None



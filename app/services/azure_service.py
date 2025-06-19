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

        self.speech_config = speechsdk.SpeechConfig(subscription=self.speech_key, region=self.region)
        self.speech_config.speech_synthesis_voice_name = self.voice
        self.speech_config.set_speech_synthesis_output_format(speechsdk.SpeechSynthesisOutputFormat.Raw8Khz8BitMonoMULaw)


    async def establish_connection(self, voice:str):
        self.speech_config.speech_synthesis_voice_name = voice

        self.speech_synthesizer = speechsdk.SpeechSynthesizer(speech_config=self.speech_config, audio_config=None)


    async def stream_text_to_speech(self, text: str, voice: str, call_id,  queue_audio=None):
        """
        Synthesizes text using Azure TTS and sends the 8kHz u-law audio
        Directly requests 8kHz u-law from Azure.
        """

        # Receives a text from console input and synthesizes it to result.
        # while True:
        print("Enter some text that you want to synthesize, Ctrl-Z to exit")
        result = self.speech_synthesizer.speak_text_async(text).get()
        # Check result
        if result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted:
            audio_data = result.audio_data
            await queue_audio(call_id, audio_data)
        elif result.reason == speechsdk.ResultReason.Canceled:
            cancellation_details = result.cancellation_details
            print("Speech synthesis canceled: {}".format(cancellation_details.reason))
            if cancellation_details.reason == speechsdk.CancellationReason.Error:
                print("Error details: {}".format(cancellation_details.error_details))
        return
        # Optional: Choose a voice. Neural voices generally sound better,
        # and Azure will handle the downsampling to 8kHz ULaw for you.

    async def flush_sp_ws(self):
        return



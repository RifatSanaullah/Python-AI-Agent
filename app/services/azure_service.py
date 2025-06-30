import azure.cognitiveservices.speech as speechsdk
from app.config import settings
import io, threading, asyncio
import re # Add this import at the top of the file

class AzureService:
    def __init__(self, loop = None):
        self.speech_key = settings.azure_key
        self.region = settings.azure_region
        self.voice = "en-US-AriaNeural"
        self.queue_audio = {}
        self.speech_synthesizer = None
        self.tts_task = None
        self.tts_request = None
        self._receiver_thread = None
        self.loop = loop
        # Initialize Azure Speech config
        self.speech_config = speechsdk.SpeechConfig(
            endpoint=f"wss://{settings.azure_region}.tts.speech.microsoft.com/cognitiveservices/websocket/v2",
            subscription=settings.azure_key
        )
        self._exit=None
        # self.speech_config = speechsdk.SpeechConfig(subscription=self.speech_key, region=self.region)
        self.speech_config.speech_synthesis_voice_name = self.voice
        self.speech_config.set_speech_synthesis_output_format(speechsdk.SpeechSynthesisOutputFormat.Raw8Khz8BitMonoMULaw)
        self.full_text_buffer = ""
        self.last_split_index=0

    # async def establish_connection(self, voice:str):f
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


    async def start_synthesiser(self):
        self.tts_request = speechsdk.SpeechSynthesisRequest(input_type=speechsdk.SpeechSynthesisRequestInputType.TextStream)
        self.tts_task = self.speech_synthesizer.speak_async(self.tts_request)
        # self._receiver_thread = threading.Thread(target=asyncio.run, args=(self.receiver(),))
        # self._receiver_thread.start()
        # self._exit = threading.Event()
        # print("Synthesiser Start")
        

    def _synthesis_completed_callback(self, evt: speechsdk.SpeechSynthesisEventArgs):
        # This indicates that the current text written to the input stream has been processed.
        # It doesn't mean no more audio will come, just that what was fed is done.
        # print("Speech synthesis completed for current input stream.")
        # You might set a flag here if you need to know when all current queued text is done.
        if evt.result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted:  
            asyncio.run_coroutine_threadsafe(
                    self.queue_audio['queue_audio'](self.queue_audio['call_id'],evt.result.audio_data),
                    self.loop
                )
        print("Speech synthesis completed.")
        
    async def update_call_id(self, call_id, queue_audio):
        
        if 'call_id' not in self.queue_audio:
                self.queue_audio = {
                    'call_id': call_id,
                    "queue_audio": queue_audio
        }
        
    async def establish_connection(self, voice:str):
        self.speech_config.speech_synthesis_voice_name = voice

        self.speech_synthesizer = speechsdk.SpeechSynthesizer(speech_config=self.speech_config, audio_config=None)
        # self.speech_synthesizer.synthesizing.connect(lambda evt: print("[audio]", end=""))
        self.speech_synthesizer.synthesis_completed.connect(self._synthesis_completed_callback)
        self.speech_synthesizer.synthesis_canceled.connect(
            lambda evt: print(f"Speech synthesis canceled: {evt.result.cancellation_details.error_details}")
        )
        await self.start_synthesiser()
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
                # self.tts_task = self.speech_synthesizer.speak_ssml_async(self.tts_request)
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

    async def stream_text_to_speech(self, text: str):
        # return self.tts_request.input_stream.write(text)
        return await self.send_to_tts(text)

    async def send_to_tts(self, text_chunk):
        
                        self.full_text_buffer += text_chunk

                        # --- Core Sentence Detection Logic ---
                        # Look for common sentence endings: period, exclamation mark, question mark
                        # This regex looks for these characters followed by either whitespace or the end of the string.
                        # It will match `. `, `!`, `?`, `.`, `!`, `?`
                        # This avoids splitting on emails like 'user@example.com' because the '.' is not followed by whitespace.
                        # It will still split on 'Dr. Smith' if a space follows the period.
                        
                        # Find all sentence endings in the current buffer
                        # re.split keeps the delimiters if you use capturing groups, but we need the index for split.
                        # The finditer method gives us the end index of the match.
                        
                        sentences_to_process = []
                        self.last_split_index = 0
                        
                        # Loop to find all complete sentences within the current buffer
                        for match in re.finditer(r'[.!?](?:\s|$)', self.full_text_buffer):
                            # The sentence goes from the last split point up to the end of this punctuation mark
                            sentence = self.full_text_buffer[self.last_split_index : match.end()].strip()
                            if sentence:
                                sentences_to_process.append(sentence)
                            self.last_split_index = match.end()

                        # If we found any complete sentences, process them
                        for sentence_to_speak in sentences_to_process:
                            self.tts_request.input_stream.write(sentence_to_speak)
                            await self.flush_sp_ws()
                        # await self._synthesize_text_chunk(text_to_synthesize, self.current_synth_id)
                            # self.full_text_buffer = ''
                            
                        # Keep any remaining text in the buffer for the next chunk
                        self.full_text_buffer = self.full_text_buffer[self.last_split_index:].strip()





    async def _synthesize_text_chunk(self, text_to_synthesize: str, synth_id: int):

            try:
                # Use SSML for more control, especially for partial text
                ssml = f"""
                        <speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis" xml:lang="en-US">
                            <voice name="{self.voice}">
                                <prosody rate="medium" pitch="medium">
                                    {text_to_synthesize}
                                </prosody>
                            </voice>
                        </speak>
                    """
                # result = self.speech_synthesizer.speak_ssml_async(ssml).get()
                print('ssml' , ssml)
                result = self.speech_synthesizer.speak_ssml(ssml)
                print('result' , result)
                
                if result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted:
                    audio_data = result.audio_data
                    await self.queue_audio['queue_audio'](self.queue_audio['call_id'],audio_data)
                    return
                else:
                    logger.error(f"TTS synthesis failed: {result.reason}")
                    print(f"TTS synthesis failed: {result.reason}")

                    return None

            except Exception as e:
                print(f"Error during Azure synthesis for chunk {synth_id}: {e}")

    async def flush_sp_ws(self):
        print("FLUSH REQUEST")
        if self.tts_request is not None:
            self.tts_request.input_stream.close()
        if self.tts_task:
                # await self.get_tts_data()
                await self.start_synthesiser()
        return
    
    async def disconnect(self):
        print("Disconnected")
        if self.tts_request is not None:
            self.tts_request.input_stream.close()
        self.tts_task = None
        self.tts_request = None
        if self._exit is not None:
            self._exit.set()
        if self._receiver_thread is not None:
            self._receiver_thread.join()
            self._receiver_thread=None



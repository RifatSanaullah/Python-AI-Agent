from google.cloud import speech
from google.cloud.speech import RecognitionConfig, StreamingRecognitionConfig
import numpy as np

class GoogleSpeechService:
    def __init__(self):
        # Initialize the client
        self.client = speech.SpeechClient()

        # Default configuration for μ-law audio
        self.config = RecognitionConfig(
            encoding=RecognitionConfig.AudioEncoding.MULAW,
            sample_rate_hertz=8000,  # Match your input format
            language_code="en-US",
        )
        self.streaming_config = StreamingRecognitionConfig(
            config=self.config,
            interim_results=True,  # Enable interim results if needed
        )

    def is_static_or_silence(self, chunk):
        """
        Checks if the audio chunk is static or silence.

        :param chunk: A μ-law encoded audio chunk.
        :return: True if the chunk is static or silence, False otherwise.
        """
        audio_data = np.frombuffer(chunk, dtype=np.uint8)
        print(f"Audio data: {np.std(audio_data)}")
        if np.std(audio_data) < 67:  # Adjust threshold as needed
            return True
        return False

    def transcribe_ulaw_chunks(self, chunk, callback):
        """
        Transcribes μ-law audio chunks in real-time.

        :param chunk: A μ-law encoded audio chunk.
        :param callback: A function to process transcription results.
        """
        if not self.client:
            print("Speech client is not initialized.")
            return
        if self.is_static_or_silence(chunk):
            print("Chunk is static or silence, skipping transcription.")
            return

        requests = (speech.StreamingRecognizeRequest(audio_content=chunk),)
        
        try:
            responses = self.client.streaming_recognize(self.streaming_config, requests)
            for response in responses:
                print(f"Received response: {response}")
                callback(response)
        except Exception as e:
            print(f"Error during streaming recognition: {e}")

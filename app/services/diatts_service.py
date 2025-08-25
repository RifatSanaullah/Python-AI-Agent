from dia.model import Dia
from app.config import settings
import websockets, asyncio, json, re, base64
from app.services.interval_runner import IntervalRunner
from app.services.ai_service import AIService
import torch
import soundfile as sf
import io
import resampy  # New import for resampling
import librosa  # New import for u-law encoding
import numpy as np  # New import for array manipulation


class DiaService:
    def __init__(self, loop=None):
        """Initialize the DiaLabs service with the pre-trained model."""
        self.model = None
        self.ws = None
        self.queue_audio = {}
        self.text_queue = asyncio.Queue()
        self.voice_id = None
        self.voice = None
        self.call_id = None
        self.ws_task = None
        self.runner = IntervalRunner()
        self.full_text_buffer = ''
        self.last_split_index = 0
        self.ai_service = AIService()
        self.is_connected = False  # Add this state variable for connection status

    async def load_model(self):
        """Load the Dia model onto the GPU."""
        try:
            # Check for CUDA availability
            if not torch.cuda.is_available():
                print("CUDA not available. Dia-1.6B requires a CUDA-enabled GPU.")
                return False

            print("Loading Dia-1.6B model...")
            self.model = Dia.from_pretrained("nari-labs/Dia-1.6B").to("cuda")
            print("Dia-1.6B model loaded successfully.")
            return True
        except Exception as e:
            print(f"Failed to load Dia model: {e}")
            return False

    async def update_call_id(self, call_id, queue_audio=None):
        self.queue_audio = queue_audio
        self.call_id = call_id

    async def establish_connection(self, voice, model_id):
        if not self.model:
            await self.load_model()

        self.voice = voice
        self.voice_id = voice['model']
        # We start a dummy task to simulate listening for a connection
        # The real server would be handled externally or in a separate method
        self.is_connected = True
        print("DiaLabsService is ready to synthesize.")

    async def stream_text_to_speech(self, text_chunk, chunk_id):
        """
        Accumulates text and processes it when a complete sentence is formed.
        This sends text to a local processing function, not an external API.
        """
        self.full_text_buffer += text_chunk
        sentences_to_process = []
        self.last_split_index = 0

        pattern = r'(?<!\.)[.!?](?![.\-])(?:\s|$)'
        for match in re.finditer(pattern, self.full_text_buffer):
            sentence = self.full_text_buffer[self.last_split_index:match.end()].strip()
            if sentence:
                sentences_to_process.append(sentence)
            self.last_split_index = match.end()

        for sentence_to_speak in sentences_to_process:
            await self.send_stream_to_tts(sentence_to_speak, chunk_id)

        self.full_text_buffer = self.full_text_buffer[self.last_split_index:].strip()

    async def send_stream_to_tts(self, text, chunk_id):
        print(f"DiaLabs: Synthesizing speech for: {text}")

        # The Dia model expects speaker tags like [S1], [S2]
        dia_text = f"[S1] {text}"

        try:
            output_tensor = self.model.generate(dia_text)
            audio_data_np = output_tensor.cpu().numpy().squeeze()

            # Dia outputs at 44.1kHz. We need to resample it to 8000Hz.
            resampled_audio = resampy.resample(audio_data_np, sr_orig=44100, sr_new=8000)
            ulaw_encoded_data = librosa.mu_law_compress(resampled_audio, quantize=256)
            ulaw_bytes = ulaw_encoded_data.astype(np.uint8).tobytes()

            chunk_size = 1000  # A smaller chunk size is better for low latency
            for i in range(0, len(ulaw_bytes), chunk_size):
                chunk = ulaw_bytes[i:i + chunk_size]
                if chunk:
                    # Send the raw u-law bytes to your audio queue
                    await self.queue_audio(self.call_id, chunk, chunk_id)

            print("Finished synthesizing and streaming sentence.")

        except Exception as e:
            print(f"DiaLabs synthesis error: {e}")

    def check_ws_connection(self):
        return self.is_connected

    async def update_tts_interrupt(self, status):
        # For Dia, you'd likely implement a way to stop the `model.generate`
        # process if possible, but this is complex.
        pass

    async def flush_sp_ws(self):
        pass

    async def disconnect(self):
        self.runner.stop_interval(self.call_id)
        if self.ws_task:
            self.ws_task.cancel()
        print("DiaLabsService disconnected and cleaned up.")


async def mock_queue_audio(call_id, audio_chunk, chunk_id):
    """A mock function to print the queued audio data and chunk ID."""
    print(f"Mock Queue Audio: call_id={call_id}, chunk_id={chunk_id}, audio_bytes_length={len(audio_chunk)}")


async def test_dia_service():
    """Main function to run the test script."""
    dia_service = DiaService()
    call_id = "test-call-123"
    voice = {'model': 'test-voice-1'}
    model_id = 'test-model-1'

    # Set up the service
    await dia_service.update_call_id(call_id, mock_queue_audio)
    await dia_service.establish_connection(voice, model_id)

    # --- Test Case 1: Simple sentence ---
    print("\n--- Running Test Case 1: Simple Sentence ---")
    text_to_send_1 = "Hello world. How are you today?"
    chunk_id_1 = "chunk-001"

    # Split the text into chunks to simulate a real-time stream
    chunk1_part1 = "Hello world."
    chunk1_part2 = " How are you today?"

    await dia_service.stream_text_to_speech(chunk1_part1, chunk_id_1)
    await dia_service.stream_text_to_speech(chunk1_part2, chunk_id_1)
    await asyncio.sleep(1)  # Give it time to process

    # --- Test Case 2: Multiple sentences with different chunk IDs ---
    print("\n--- Running Test Case 2: Multiple Sentences with Different Chunk IDs ---")
    text_to_send_2 = "This is a new sentence. It should have a new ID."
    chunk_id_2 = "chunk-002"

    await dia_service.stream_text_to_speech("This is a new sentence.", chunk_id_2)
    await dia_service.stream_text_to_speech(" It should have a new ID.", chunk_id_2)
    await asyncio.sleep(1)  # Give it time to process

    # --- Test Case 3: Incomplete sentence test ---
    print("\n--- Running Test Case 3: Incomplete Sentence Test ---")
    chunk_id_3 = "chunk-003"
    await dia_service.stream_text_to_speech("This is an incomplete", chunk_id_3)
    await dia_service.stream_text_to_speech(" sentence", chunk_id_3)

    # The last chunk to complete the sentence
    await dia_service.stream_text_to_speech(".", chunk_id_3)
    await asyncio.sleep(1)  # Give it time to process

    # Disconnect when done
    await dia_service.disconnect()


if __name__ == "__main__":
    asyncio.run(test_dia_service())
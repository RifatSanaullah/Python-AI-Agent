# from dia.model import Dia
# from app.config import settings
# import websockets, asyncio, json, re, base64
# from app.services.interval_runner import IntervalRunner
# from app.services.ai_service import AIService
# import torch
# import soundfile as sf
# import io
# import resampy  # New import for resampling
# import librosa  # New import for u-law encoding
# import numpy as np  # New import for array manipulation
# import os

# os.environ['HF_HUB_DISABLE_SYMLINKS_WARNING'] = '1'

# class DiaService:
#     def __init__(self, loop=None):
#         """Initialize the DiaLabs service with the pre-trained model."""
#         self.model = None
#         self.ws = None
#         self.queue_audio = {}
#         self.text_queue = asyncio.Queue()
#         self.voice_id = None
#         self.voice = None
#         self.call_id = None
#         self.ws_task = None
#         self.runner = IntervalRunner()
#         self.full_text_buffer = ''
#         self.last_split_index = 0
#         self.ai_service = AIService()
#         self.is_connected = False  # Add this state variable for connection status

#     async def load_model(self):
#         """Load the Dia model onto the GPU."""
#         try:
#             print("Loading Dia-1.6B model...")
#             self.model = Dia.from_pretrained("nari-labs/Dia-1.6B-0626", compute_dtype="float16")
#             print("Dia-1.6B model loaded successfully.")
#             return True
#         except Exception as e:
#             print(f"Failed to load Dia model: {e}")
#             return False

#     async def update_call_id(self, call_id, queue_audio=None):
#         self.queue_audio = queue_audio
#         self.call_id = call_id

#     async def establish_connection(self, voice, model_id):
#         if not self.model:
#             model_loaded = await self.load_model()
#             if not model_loaded:
#                 print("Failed to load model. Exiting.")
#                 return  # Stop execution if the model didn't load
        
#         self.voice = voice
#         self.voice_id = voice['model']
#         self.is_connected = True
#         print("DiaLabsService is ready to synthesize.")

#     async def stream_text_to_speech(self, text_chunk, chunk_id):
#         """
#         Accumulates text and processes it when a complete sentence is formed.
#         This sends text to a local processing function, not an external API.
#         """
#         self.full_text_buffer += text_chunk
#         sentences_to_process = []
#         self.last_split_index = 0

#         pattern = r'(?<!\.)[.!?](?![.\-])(?:\s|$)'
#         for match in re.finditer(pattern, self.full_text_buffer):
#             sentence = self.full_text_buffer[self.last_split_index:match.end()].strip()
#             if sentence:
#                 sentences_to_process.append(sentence)
#             self.last_split_index = match.end()

#         for sentence_to_speak in sentences_to_process:
#             await self.send_stream_to_tts(sentence_to_speak, chunk_id)

#         self.full_text_buffer = self.full_text_buffer[self.last_split_index:].strip()

#     async def send_stream_to_tts(self, text, chunk_id):
#         print(f"DiaLabs: Synthesizing speech for: {text}")

#         # The Dia model expects speaker tags like [S1], [S2]
#         dia_text = f"[S1] {text}"

#         try:
#             output_tensor = self.model.generate(dia_text,
#                 use_torch_compile=False,
#                 verbose=True,
#                 cfg_scale=3.0,
#                 temperature=1.8,
#                 top_p=0.90,
#                 cfg_filter_top_k=50,)
#             audio_data_np = output_tensor.cpu().numpy().squeeze()

#             # Dia outputs at 44.1kHz. We need to resample it to 8000Hz.
#             resampled_audio = resampy.resample(audio_data_np, sr_orig=44100, sr_new=8000)
#             ulaw_encoded_data = librosa.mu_law_compress(resampled_audio, quantize=256)
#             ulaw_bytes = ulaw_encoded_data.astype(np.uint8).tobytes()

#             chunk_size = 1000  # A smaller chunk size is better for low latency
#             for i in range(0, len(ulaw_bytes), chunk_size):
#                 chunk = ulaw_bytes[i:i + chunk_size]
#                 if chunk:
#                     # Send the raw u-law bytes to your audio queue
#                     await self.queue_audio(self.call_id, chunk, chunk_id)

#             print("Finished synthesizing and streaming sentence.")

#         except Exception as e:
#             print(f"DiaLabs synthesis error: {e}")

#     def check_ws_connection(self):
#         return self.is_connected

#     async def update_tts_interrupt(self, status):
#         # For Dia, you'd likely implement a way to stop the `model.generate`
#         # process if possible, but this is complex.
#         pass

#     async def flush_sp_ws(self):
#         pass

#     async def disconnect(self):
#         self.runner.stop_interval(self.call_id)
#         if self.ws_task:
#             self.ws_task.cancel()
#         print("DiaLabsService disconnected and cleaned up.")


# async def mock_queue_audio(call_id, audio_chunk, chunk_id):
#     """A mock function to print the queued audio data and chunk ID."""
#     print(f"Mock Queue Audio: call_id={call_id}, chunk_id={chunk_id}, audio_bytes_length={len(audio_chunk)}")


# async def test_dia_service():
#     """Main function to run the test script."""
#     dia_service = DiaService()
#     call_id = "test-call-123"
#     voice = {'model': 'test-voice-1'}
#     model_id = 'test-model-1'

#     # Set up the service
#     await dia_service.update_call_id(call_id, mock_queue_audio)
#     print("call id updated")
#     await dia_service.establish_connection(voice, model_id)

#     # --- Test Case 1: Simple sentence ---
#     print("\n--- Running Test Case 1: Simple Sentence ---")
#     text_to_send_1 = "Hello world. How are you today?"
#     chunk_id_1 = "chunk-001"

#     text_to_send_2 = "You are Samara, a licensed realtor with 20 years of experience at Summit Home Realty, serving Southern California — including Los Angeles, Orange County, San Bernardino, San Diego, and Santa Barbara."
#     chunk_id_2 = "chunk-002"

#     await dia_service.stream_text_to_speech(text_to_send_1, chunk_id_1)
#     await asyncio.sleep(1)

#     await dia_service.stream_text_to_speech(text_to_send_2, chunk_id_2)
#     await asyncio.sleep(1)


#     # Disconnect when done
#     await dia_service.disconnect()


# if __name__ == "__main__":
#     asyncio.run(test_dia_service())



from dia.model import Dia
from app.config import settings
import websockets, asyncio, json, re, base64
from app.services.interval_runner import IntervalRunner
from app.services.ai_service import AIService
import torch
import soundfile as sf
import io
import resampy
import librosa
import numpy as np
import os
import wave

os.environ['HF_HUB_DISABLE_SYMLINKS_WARNING'] = '1'

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
        self.is_connected = False
        self.audio_buffer = []
        self.generation_task = None
        self.stop_generation = False

    async def load_model(self):
        """Load the Dia model onto the GPU with optimizations."""
        try:
            print("Loading Dia-1.6B model with optimizations...")
            
            # Load with basic parameters (remove unsupported ones)
            self.model = Dia.from_pretrained(
                "nari-labs/Dia-1.6B-0626", 
                compute_dtype="float16",
            )
            
            print("Dia-1.6B model loaded successfully with optimizations.")
            return True
        except Exception as e:
            print(f"Failed to load Dia model: {e}")
            import traceback
            traceback.print_exc()
            return False

    async def update_call_id(self, call_id, queue_audio=None):
        self.queue_audio = queue_audio
        self.call_id = call_id

    async def establish_connection(self, voice, model_id):
        if not self.model:
            model_loaded = await self.load_model()
            if not model_loaded:
                print("Failed to load model. Exiting.")
                return
        
        self.voice = voice
        self.voice_id = voice['model']
        self.is_connected = True
        print("DiaLabsService is ready to synthesize.")

    async def stream_text_to_speech(self, text_chunk, chunk_id):
        """
        Accumulates text and processes it when a complete sentence is formed.
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

        # Process sentences asynchronously
        for sentence_to_speak in sentences_to_process:
            # Start generation in background without waiting
            asyncio.create_task(self.send_stream_to_tts(sentence_to_speak, chunk_id))

        self.full_text_buffer = self.full_text_buffer[self.last_split_index:].strip()

    async def send_stream_to_tts(self, text, chunk_id):
        print(f"DiaLabs: Synthesizing speech for: {text}")

        # The Dia model expects speaker tags like [S1], [S2]
        dia_text = f"[S1] {text}"

        try:
            # Generate audio with fewer steps for faster generation
            # Try to use the minimal set of parameters that work
            generation_params = {
                "use_torch_compile": False,  # Start with False to avoid issues
                "verbose": False,
            }
            
            # Try to add parameters that might be supported
            try:
                # These parameters might speed up generation if supported
                generation_params.update({
                    "cfg_scale": 2.5,
                    "temperature": 1.5,
                    "top_p": 0.85,
                    "cfg_filter_top_k": 30,
                })
            except:
                print("Some optimization parameters not supported, using defaults")
                
            output = self.model.generate(dia_text, **generation_params)
            self.model.save_audio("simple.mp3", output)
            # Handle different return types - tensor or numpy array
            if hasattr(output, 'cpu'):
                # It's a tensor, convert to numpy
                audio_data_np = output.cpu().numpy().squeeze()
            else:
                # It's already a numpy array
                audio_data_np = output.squeeze()
                
            print(f"Generated audio: {audio_data_np.shape}")

            # Save the original 44.1kHz audio
            self.audio_buffer.append(audio_data_np)
            
            # Stream the audio
            await self.stream_audio(audio_data_np, chunk_id)

            print("Finished synthesizing and streaming sentence.")

        except Exception as e:
            print(f"DiaLabs synthesis error: {e}")
            import traceback
            traceback.print_exc()
    
    async def stream_audio(self, audio_data_np, chunk_id):
        """Stream audio in chunks."""
        # Resample to 8000Hz for streaming
        resampled_audio = resampy.resample(audio_data_np, sr_orig=44100, sr_new=8000)
        
        # Apply u-law compression for telephone-quality audio
        # FIX: Use librosa.mu_compress instead of librosa.mu_law_compress
        ulaw_encoded_data = librosa.mu_compress(resampled_audio, quantize=True)
        ulaw_bytes = ulaw_encoded_data.astype(np.uint8).tobytes()

        # Stream in small chunks
        stream_chunk_size = 1000
        for j in range(0, len(ulaw_bytes), stream_chunk_size):
            if self.stop_generation:
                break
                
            stream_chunk = ulaw_bytes[j:j + stream_chunk_size]
            if stream_chunk:
                await self.queue_audio(self.call_id, stream_chunk, chunk_id)
            
            # Small delay to simulate real-time streaming
            await asyncio.sleep(0.01)

    def check_ws_connection(self):
        return self.is_connected

    async def update_tts_interrupt(self, status):
        # Set flag to stop current generation
        self.stop_generation = True
        # Reset flag after a short delay
        await asyncio.sleep(0.1)
        self.stop_generation = False

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
    print("call id updated")
    await dia_service.establish_connection(voice, model_id)

    # --- Test Case 1: Simple sentence ---
    print("\n--- Running Test Case 1: Simple Sentence ---")
    text_to_send_1 = "Hello world."
    chunk_id_1 = "chunk-001"

    await dia_service.stream_text_to_speech(text_to_send_1, chunk_id_1)
    await asyncio.sleep(15)  # Give it time to process

    # Disconnect when done
    await dia_service.disconnect()


if __name__ == "__main__":
    asyncio.run(test_dia_service())
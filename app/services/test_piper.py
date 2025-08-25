import asyncio
import io
import wave
from pipertts_service import PiperService
from pydub import AudioSegment

# Mock function for saving the audio
async def mock_queue_audio(call_id, audio_data, chunk_id):
    """
    This function simulates the audio queue. It will save the audio
    to a file instead of sending it over a network.
    """
    print(f"Received audio chunk for call_id: {call_id}, chunk_id: {chunk_id}")

    # Define a filename based on the chunk ID
    filename = f"output_audio_{chunk_id}.ulaw"

    # Save the audio data to a file in binary mode
    try:
        with open(filename, 'wb') as f:
            f.write(audio_data)
        print(f"Audio saved to {filename}")

    except Exception as e:
        print(f"Error saving file: {e}")

    # You can also convert and save to WAV for easier playback
    try:
        # Pydub needs a file-like object or a path to read from
        audio_segment = AudioSegment.from_file(io.BytesIO(audio_data), format="ulaw", frame_rate=8000, channels=1)
        wav_filename = f"output_audio_{chunk_id}.wav"
        audio_segment.export(wav_filename, format="wav")
        print(f"Audio also saved to {wav_filename}")
    except Exception as e:
        print(f"Error converting and saving to WAV: {e}")


async def main():
    # Instantiate the PiperService
    piper_service = PiperService()

    # Define some test text and a chunk ID
    test_text = "Hello, this is a test from your Piper service. The audio is now being generated locally and converted to the correct format."
    chunk_id = "test_123"

    # Call the update_call_id method, passing our mock function
    await piper_service.update_call_id(call_id="my_test_call", queue_audio=mock_queue_audio)

    # Establish the connection (placeholder for Piper)
    await piper_service.establish_connection(voice="test_voice", model_id="test_model")

    # Call the main streaming function with the test text
    await piper_service.stream_text_to_speech(test_text, chunk_id)

    # Disconnect the service
    await piper_service.disconnect()


if __name__ == "__main__":
    # Ensure you are running with an appropriate version of Python (3.7+)
    asyncio.run(main())
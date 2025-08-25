from RealtimeTTS import TextToAudioStream, EdgeEngine
import os

def dummy_generator():
    yield "Hey guys! These here are realtime spoken sentences based on local text synthesis. "
    yield "With a local, neuronal, cloned voice. So every spoken sentence sounds unique."

print("Starting engines")
edge_engine = EdgeEngine()
stream = TextToAudioStream(edge_engine)
stream.feed(dummy_generator())
stream.play(output_wavfile=stream.engine.engine_name + "_output.mp3")
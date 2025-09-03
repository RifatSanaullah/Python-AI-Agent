import torch
import torchaudio
import librosa
import asyncio
import os
import logging
from transformers import AutoFeatureExtractor, AutoModelForAudioClassification

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class VoiceMailDetection:
    """
    Asynchronous class for voicemail detection using a pre-trained model.
    The heavy-lifting of classification is offloaded to a thread to prevent blocking the event loop.
    """
    def __init__(self):
        # Set the audio backend for torchaudio
        torchaudio.set_audio_backend("soundfile")

        # Load the pre-trained model and processor.
        # This is a synchronous operation and is done once during initialization.
        logging.info("Loading feature extractor and model...")
        self.processor = AutoFeatureExtractor.from_pretrained("jakeBland/wav2vec-vm-finetune")
        self.model = AutoModelForAudioClassification.from_pretrained("jakeBland/wav2vec-vm-finetune")
        self.model.eval()
        logging.info("Model loaded successfully.")

    def _load_audio_sync(self, audio_path, load_rate=8000, target_rate=16000):
        """
        Synchronous helper function to load and resample audio.
        This function runs in a separate thread.
        """
        if not os.path.exists(audio_path):
            raise FileNotFoundError(f"Audio file not found at: {audio_path}")
            
        logging.info(f"Loading audio file: {audio_path}")
        waveform, sr = librosa.load(audio_path, sr=load_rate, mono=True)
        if sr != target_rate:
            logging.info(f"Resampling audio from {sr} Hz to {target_rate} Hz.")
            waveform = librosa.resample(waveform, orig_sr=sr, target_sr=target_rate)
        
        return torch.tensor(waveform).unsqueeze(0), target_rate

    def _classify_audio_sync(self, waveform, sample_rate):
        """
        Synchronous helper function for audio classification.
        This function performs the model inference and runs in a separate thread.
        """
        logging.info("Starting audio classification.")
        inputs = self.processor(
            waveform.squeeze().numpy(),
            sampling_rate=sample_rate,
            return_tensors="pt",
            padding=True
        )

        with torch.no_grad():
            outputs = self.model(**inputs)
            predictions = torch.nn.functional.softmax(outputs.logits, dim=-1).squeeze()

        predicted_class_idx = predictions.argmax().item()
        confidence = predictions.max().item()
        predicted_label = self.model.config.id2label.get(predicted_class_idx, f"Class {predicted_class_idx}")
        
        logging.info("Classification complete.")
        return predicted_label, confidence

    async def process_voicemail(self, audio_file):
        """
        The main asynchronous method to process a voicemail file.
        It uses asyncio.to_thread() to offload the blocking operations.
        """
        try:
            # Load and resample audio in a separate thread
            waveform, sample_rate = await asyncio.to_thread(self._load_audio_sync, audio_file)

            # Classify the audio in a separate thread
            label, confidence = await asyncio.to_thread(self._classify_audio_sync, waveform, sample_rate)
            
            return label, confidence
        except Exception as e:
            logging.error(f"An error occurred during voicemail processing: {e}")
            return "error", 0.0

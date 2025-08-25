
import audioop
import numpy as np
from collections import deque
import time

from typing import Callable, Optional

class VoiceActivityDetector:
    def __init__(self, 
                 sample_rate: int = 8000,
                 frame_duration_ms: int = 30,
                 energy_threshold: float = 500.0,
                 silence_duration_ms: int = 800,
                 voice_duration_ms: int = 300):
        """
        Initialize Voice Activity Detection
        
        Args:
            sample_rate: Audio sample rate (Twilio uses 8kHz)
            frame_duration_ms: Frame duration in milliseconds
            energy_threshold: Energy threshold for voice detection
            silence_duration_ms: Duration of silence to confirm voice stopped
            voice_duration_ms: Duration of voice to confirm voice started
        """
        self.sample_rate = sample_rate
        self.frame_duration_ms = frame_duration_ms
        self.frame_size = int(sample_rate * frame_duration_ms / 1000)
        self.energy_threshold = energy_threshold
        self.silence_duration_ms = silence_duration_ms
        self.voice_duration_ms = voice_duration_ms
        
        # State tracking
        self.audio_buffer = deque(maxlen=self.frame_size * 2)
        self.energy_history = deque(maxlen=10)
        self.voice_detected = False
        self.last_voice_time = 0
        self.voice_start_time = 0
        
        # Callbacks
        self.on_voice_start: Optional[Callable] = None
        self.on_voice_end: Optional[Callable] = None
        
    def mulaw_to_linear(self, mulaw_data: bytes) -> np.ndarray:
        """Convert mulaw audio to linear PCM"""
        # Convert mulaw to linear PCM (16-bit)
        linear_data = audioop.ulaw2lin(mulaw_data, 2)  # 2 bytes per sample
        # Convert to numpy array
        audio_array = np.frombuffer(linear_data, dtype=np.int16)
        return audio_array.astype(np.float32)
    
    def calculate_energy(self, audio_frame: np.ndarray) -> float:
        """Calculate energy of audio frame"""
        if len(audio_frame) == 0:
            return 0.0
        return np.sqrt(np.mean(audio_frame ** 2))
    
    def adaptive_threshold(self) -> float:
        """Calculate adaptive threshold based on recent energy history"""
        if len(self.energy_history) < 5:
            return self.energy_threshold
        
        avg_energy = np.mean(self.energy_history)
        return max(self.energy_threshold, avg_energy * 2.0)
    
    def process_audio_chunk(self, mulaw_chunk: bytes) -> bool:
        """
        Process incoming mulaw audio chunk
        
        Args:
            mulaw_chunk: Raw mulaw audio bytes from Twilio
            
        Returns:
            bool: Current voice activity status
        """
        # Convert mulaw to linear
        linear_audio = self.mulaw_to_linear(mulaw_chunk)
        
        # Add to buffer
        self.audio_buffer.extend(linear_audio)
        
        # Process if we have enough samples
        if len(self.audio_buffer) >= self.frame_size:
            # Get frame
            frame = np.array(list(self.audio_buffer)[:self.frame_size])
            
            # Calculate energy
            energy = self.calculate_energy(frame)
            self.energy_history.append(energy)
            
            # Get adaptive threshold
            threshold = self.adaptive_threshold()
            
            current_time = time.time() * 1000  # Convert to milliseconds
            
            # Voice activity detection logic
            if energy > threshold:
                if not self.voice_detected:
                    if self.voice_start_time == 0:
                        self.voice_start_time = current_time
                    elif current_time - self.voice_start_time > self.voice_duration_ms:
                        # Voice confirmed
                        self.voice_detected = True
                        if self.on_voice_start:
                            self.on_voice_start()
                
                self.last_voice_time = current_time
            else:
                if self.voice_detected:
                    if current_time - self.last_voice_time > self.silence_duration_ms:
                        # Silence confirmed
                        self.voice_detected = False
                        self.voice_start_time = 0
                        if self.on_voice_end:
                            self.on_voice_end()
                else:
                    self.voice_start_time = 0
            
            # Remove processed samples
            for _ in range(min(self.frame_size, len(self.audio_buffer))):
                self.audio_buffer.popleft()
        
        return self.voice_detected
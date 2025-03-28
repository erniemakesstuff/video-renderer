import copy
import math
from pathlib import Path
import random
from types import SimpleNamespace
import os
import json
import logging
from typing import List

from botocore.exceptions import ClientError
from moviepy import *
import numpy as np
import scipy
import torch
import whisper_timestamped as whisper
from transformers import AutoProcessor, MusicgenForConditionalGeneration

logger = logging.getLogger(__name__)

class MusicScoring(object):
    
    def __init__(self, model_name="facebook/musicgen-stereo-small", total_duration=120):
        """
        Initialize MusicGen generator with sliding window approach
        
        :param model_name: Pretrained MusicGen model name
        :param total_duration: Total desired music duration in seconds
        """
        self.processor = AutoProcessor.from_pretrained(model_name)
        self.model = MusicgenForConditionalGeneration.from_pretrained(model_name)
        
        # Configuration
        self.sampling_rate = self.model.config.audio_encoder.sampling_rate
        self.max_generation_duration = 30  # Maximum generation duration in seconds
        self.sliding_window_duration = 10  # Duration of sliding window in seconds
        self.total_desired_duration = total_duration

    
    def score_media(self, prompt, sourceMediaID, callbackMediaID) -> bool:
        # 1. Download media.
        # 2. collect noteable times.
        # 3. Generate music.
        # 4. Apply music to final output media; crossfade sfx, etc.
        # 5. Upload to s3 by callbackMediaID.
        pass

    def generate_music(self, prompts):
        """
        Enhanced music generation with improved context preservation
        
        :param prompts: List of text prompts for music generation
        :return: Numpy array of generated audio
        """
        # Prepare initial inputs
        inputs = self.processor(
            text=prompts,
            padding=True,
            return_tensors="pt",
        )
        
        # Increased context preservation parameters
        tokens_per_generation = 1500  # ~30 seconds
        context_overlap_ratio = 0.5  # 50% overlap between windows
        context_window_duration = 20  # Increased context window to 20 seconds
        
        # Initialize output audio array
        full_audio = []
        
        # Initial generation
        initial_audio_values = self.model.generate(**inputs, max_new_tokens=tokens_per_generation)
        initial_audio = initial_audio_values[0, 0].numpy()
        
        # Ensure stereo 
        if initial_audio.ndim == 1:
            initial_audio = np.column_stack([initial_audio, initial_audio])
        
        full_audio.extend(initial_audio)
        
        # More sophisticated context management
        context_window = initial_audio
        
        while len(full_audio) < int(self.sampling_rate * self.total_desired_duration):
            # Prepare context input with more sophisticated approach
            context_input = self.processor(
                audio=[context_window.T], 
                sampling_rate=self.sampling_rate,
                return_tensors="pt"
            )
            
            # Advanced context merging
            merged_inputs = {
                **inputs,
                **{k: v for k, v in context_input.items() if k in ['input_features']}
            }
            
            # Generate next segment with enhanced context
            next_audio_values = self.model.generate(
                **merged_inputs,
                max_new_tokens=tokens_per_generation,
                # Optional: Add temperature for controlled randomness
                temperature=0.7
            )
            
            # Convert to numpy
            next_audio = next_audio_values[0, 0].numpy()
            
            # Ensure stereo
            if next_audio.ndim == 1:
                next_audio = np.column_stack([next_audio, next_audio])
            
            # Intelligent overlap handling
            overlap_samples = int(len(next_audio) * context_overlap_ratio)
            crossfaded_audio = self._crossfade_segments(
                context_window[-overlap_samples:], 
                next_audio, 
                overlap_samples
            )
            
            # Append new segment
            full_audio.extend(crossfaded_audio)
            
            # Update context window
            context_window = next_audio[-int(self.sampling_rate * context_window_duration):]
        
        # Trim to desired duration
        full_audio = np.array(full_audio[:int(self.sampling_rate * self.total_desired_duration)])
        
        return full_audio

    def _crossfade_segments(self, segment1, segment2, overlap_samples):
        """
        Create a smooth crossfade between two audio segments
        
        :param segment1: First audio segment
        :param segment2: Second audio segment
        :param overlap_samples: Number of samples to crossfade
        :return: Crossfaded audio segment
        """
        # Create linear crossfade weights
        fade_in = np.linspace(0, 1, overlap_samples)
        fade_out = 1 - fade_in
        
        # Apply crossfade
        crossfaded = (
            segment1[-overlap_samples:] * fade_out[:, np.newaxis] + 
            segment2[:overlap_samples] * fade_in[:, np.newaxis]
        )
        
        # Combine segments
        return np.concatenate([
            segment1[:-overlap_samples], 
            crossfaded, 
            segment2[overlap_samples:]
        ])
        
    def save_audio(self, audio_data, filename="generated_music.wav"):
        """
        Save generated audio to a WAV file
        
        :param audio_data: Numpy array of audio data
        :param filename: Output filename
        """
        scipy.io.wavfile.write(filename, rate=self.sampling_rate, data=audio_data)



    def generate_music_test(self):
        # TODO: Move this to singleton; shared reference w/ shared lock.
        processor = AutoProcessor.from_pretrained("facebook/musicgen-stereo-small")
        model = MusicgenForConditionalGeneration.from_pretrained("facebook/musicgen-stereo-small")

        inputs = processor(
            text=["80s pop track with bassy drums and synth", "90s rock song with loud guitars and heavy drums"],
            padding=True,
            return_tensors="pt",
        )
        audio_values = model.generate(**inputs, max_new_tokens=1500)

        # save .wav out
        sampling_rate = model.config.audio_encoder.sampling_rate
        scipy.io.wavfile.write("musicgen_1.5k_out.wav", rate=sampling_rate, data=audio_values[0, 0].numpy())

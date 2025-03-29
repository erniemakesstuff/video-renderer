import random
import os
import logging
import numpy as np
import torch
import scipy.io.wavfile
import platform
from transformers import AutoProcessor, MusicgenForConditionalGeneration
from pydub import AudioSegment

logger = logging.getLogger(__name__)

class MusicGeneration(object):

    def __new__(cls):
        if not hasattr(cls, 'instance'):
            cls.instance = super(MusicGeneration, cls).__new__(cls)
        return cls.instance
    # 20min, 3 generations 200sec, 60, 30 -- small model
    def __init__(self, model_name="facebook/musicgen-stereo-medium"):
        """
        Initialize MusicGen generator with optimized performance
        
        :param model_name: Pretrained MusicGen model name
        """
        # Disable gradient calculations during inference
        torch.set_grad_enabled(False)
        
        # Determine device
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        logger.info(f"Using device: {self.device}")
        
        # Load model and processor
        self.processor = AutoProcessor.from_pretrained(model_name)
        self.model = MusicgenForConditionalGeneration.from_pretrained(model_name)
        
        # Move model to GPU and optimize
        self.model = self.model.to(self.device)
        
        # Use half-precision for faster inference if on GPU
        if self.device == "cuda":
            self.model = self.model.half()  # Convert to FP16
            logger.info("Using half precision (FP16) for faster inference")
            
        # torch.compile is only used for non-Windows platforms
        if hasattr(torch, 'compile') and platform.system() != "Windows":
            try:
                self.model = torch.compile(self.model)
                logger.info("Using torch.compile for model optimization")
            except Exception as e:
                logger.warning(f"Could not use torch.compile: {e}")
        
        # Configuration
        self.sampling_rate = self.model.config.audio_encoder.sampling_rate
        self.max_generation_duration = 30  # Maximum generation duration in seconds
        self.sliding_window_duration = 10  # Reduced duration for faster processing
        
    def generate_music(self, prompts, duration_sec):
        """
        Generate music with optimized performance
        
        :param prompts: Text prompt describing the desired music
        :param duration_sec: Total desired music duration in seconds
        :return: Generated audio as numpy array
        """
        # Prepare initial inputs and move to GPU
        inputs = self.processor(
            text=prompts,
            padding=True,
            return_tensors="pt",
        )
        inputs = {k: v.to(self.device) for k, v in inputs.items()}
        
        # Optimize parameters for faster generation
        tokens_per_generation = 1200  # Slightly reduced for faster processing
        context_overlap_ratio = 0.3  # Reduced overlap for faster processing
        context_window_duration = self.sliding_window_duration
        
        # Generate initial segment
        with torch.no_grad():  # Explicitly disable gradients for inference
            initial_audio_values = self.model.generate(
                **inputs, 
                max_new_tokens=tokens_per_generation,
                temperature=0.7
            )
        
        # Convert to numpy and move to CPU
        initial_audio = initial_audio_values[0, 0].cpu().numpy()
        
        # Ensure stereo 
        if initial_audio.ndim == 1:
            initial_audio = np.column_stack([initial_audio, initial_audio])
        
        # Initialize output audio array with the initial segment
        full_audio = list(initial_audio)
        
        # Context management
        context_window = initial_audio
        
        # Determine how many segments we need to generate
        target_samples = int(self.sampling_rate * duration_sec)
        current_samples = len(full_audio)
        
        # Maximum batch size based on GPU memory
        # Adjust this value based on your GPU memory capacity
        max_batch_size = 3 if self.device == "cuda" else 1
        
        while current_samples < target_samples:
            # Calculate remaining segments needed
            remaining_samples = target_samples - current_samples
            segment_length = len(initial_audio) // 2  # Approximate length after crossfade
            remaining_segments = (remaining_samples // segment_length) + 1
            
            # Determine batch size for this iteration
            batch_size = min(max_batch_size, remaining_segments)
            
            # True parallel batch processing with multiple contexts
            if batch_size > 1:
                # Prepare batch inputs - same text prompt for all
                batch_text_inputs = {
                    k: v.repeat(batch_size, 1) if v.dim() > 1 else v.repeat(batch_size) 
                    for k, v in inputs.items()
                }
                
                # Prepare audio context input
                batch_audio_contexts = [context_window.T] * batch_size
                
                # Process all audio contexts in a single call
                batch_context_inputs = self.processor(
                    audio=batch_audio_contexts,
                    sampling_rate=self.sampling_rate,
                    return_tensors="pt"
                )
                batch_context_inputs = {
                    k: v.to(self.device) for k, v in batch_context_inputs.items() 
                    if k in ['input_features']
                }
                
                # Merge text and audio context inputs
                merged_inputs = {
                    **batch_text_inputs,
                    **batch_context_inputs
                }
                
                # Generate all segments in parallel with a single model call
                with torch.no_grad():
                    batch_audio_values = self.model.generate(
                        **merged_inputs,
                        max_new_tokens=tokens_per_generation,
                        temperature=0.7
                    )
                
                # Process each generated segment
                for i in range(batch_size):
                    # Convert to numpy
                    next_audio = batch_audio_values[i, 0].cpu().numpy()
                    
                    # Ensure stereo
                    if next_audio.ndim == 1:
                        next_audio = np.column_stack([next_audio, next_audio])
                    
                    # Calculate overlap
                    overlap_samples = int(len(next_audio) * context_overlap_ratio)
                    
                    # Apply crossfade
                    crossfaded_audio = self._efficient_crossfade(
                        context_window[-overlap_samples:], 
                        next_audio, 
                        overlap_samples
                    )
                    
                    # Append new segment
                    full_audio.extend(crossfaded_audio)
                    current_samples = len(full_audio)
                    
                    # Update context window for next iteration
                    context_window = next_audio[-int(self.sampling_rate * context_window_duration):]
                    
                    # Break if we've reached the target duration
                    if current_samples >= target_samples:
                        break
            
            else:
                # Single segment generation (same as before)
                context_input = self.processor(
                    audio=[context_window.T],
                    sampling_rate=self.sampling_rate,
                    return_tensors="pt"
                )
                context_input = {
                    k: v.to(self.device) for k, v in context_input.items() 
                    if k in ['input_features']
                }
                
                # Merge inputs
                merged_inputs = {
                    **inputs,
                    **context_input
                }
                
                # Generate
                with torch.no_grad():
                    next_audio_values = self.model.generate(
                        **merged_inputs,
                        max_new_tokens=tokens_per_generation,
                        temperature=0.7
                    )
                
                # Convert to numpy
                next_audio = next_audio_values[0, 0].cpu().numpy()
                
                # Ensure stereo
                if next_audio.ndim == 1:
                    next_audio = np.column_stack([next_audio, next_audio])
                
                # Calculate overlap
                overlap_samples = int(len(next_audio) * context_overlap_ratio)
                
                # Apply crossfade
                crossfaded_audio = self._efficient_crossfade(
                    context_window[-overlap_samples:], 
                    next_audio, 
                    overlap_samples
                )
                
                # Append new segment
                full_audio.extend(crossfaded_audio)
                current_samples = len(full_audio)
                
                # Update context window
                context_window = next_audio[-int(self.sampling_rate * context_window_duration):]
        
        # Trim to desired duration
        full_audio = np.array(full_audio[:target_samples])
        
        return full_audio

    def _efficient_crossfade(self, segment1, segment2, overlap_samples):
        """
        Create a smooth crossfade between two audio segments with optimized calculation
        
        :param segment1: First audio segment
        :param segment2: Second audio segment
        :param overlap_samples: Number of samples to crossfade
        :return: Processed audio segment
        """
        # Create linear crossfade weights (pre-calculated for efficiency)
        fade_in = np.linspace(0, 1, overlap_samples)[:, np.newaxis]
        fade_out = 1 - fade_in
        
        # Apply crossfade (vectorized operations)
        crossfaded = segment1[-overlap_samples:] * fade_out + segment2[:overlap_samples] * fade_in
        
        # Return only non-overlapping part of segment1 + crossfaded + rest of segment2
        return np.concatenate([segment1[:-overlap_samples], crossfaded, segment2[overlap_samples:]])
        
    def save_audio(self, audio_data, filename):
        """
        Save generated audio to MP3 file efficiently
        
        :param audio_data: Numpy array of audio data
        :param filename: Output filename
        """
        # Direct conversion to MP3 without temporary file
        try:
            # For stereo audio
            if audio_data.ndim > 1:
                channels = 2
                # Ensure correct format - int16 is most compatible with pydub
                audio_data = (audio_data * 32767).astype(np.int16)
            else:
                channels = 1
                audio_data = (audio_data * 32767).astype(np.int16)
                
            audio = AudioSegment(
                audio_data.tobytes(),
                frame_rate=self.sampling_rate,
                sample_width=2,  # 16-bit
                channels=channels
            )
            audio.export(filename, format="mp3")
            
        except Exception as e:
            # Fallback to scipy method with temporary file if direct conversion fails
            logger.warning(f"Direct MP3 conversion failed: {e}. Using fallback method.")
            temp_wav = f"temp_audio_{random.randint(0, 1000)}.wav"
            scipy.io.wavfile.write(temp_wav, rate=self.sampling_rate, data=audio_data)
            
            audio = AudioSegment.from_wav(temp_wav)
            audio.export(filename, format="mp3")
            
            if os.path.exists(temp_wav):
                os.remove(temp_wav)
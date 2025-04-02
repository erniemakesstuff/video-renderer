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
    
    def __init__(self, model_name="facebook/musicgen-stereo-small"):
        if hasattr(self, 'processor'):
            return  # Already initialized

        torch.set_grad_enabled(False)
        self.device = "cuda" if torch.cuda.is_available() else None
        if self.device is None:
            raise Exception("GPU is required for generation, but none is available.")
        logger.info(f"Using device: {self.device}")

        self.processor = AutoProcessor.from_pretrained(model_name)
        self.model = MusicgenForConditionalGeneration.from_pretrained(model_name).to(self.device).half()
        logger.info("Using half precision (FP16) for faster inference")

        self.sampling_rate = self.model.config.audio_encoder.sampling_rate
        self.max_generation_duration = 30
        self.sliding_window_duration = 10
        # Get number of audio channels from model config
        self.num_channels = 2  # Stereo audio has 2 channels

        self.default_params = {
            "temperature": 1.0,
            "top_k": 250,
            "top_p": 0.95,
            "guidance_scale": 3.0,
        }
        
    def enhance_prompt(self, prompt):
        if len(prompt.split()) < 5:
            descriptors = [
                "with dynamic range", "with clear melody",
                "with balanced frequencies", "with natural progression",
                "with proper mixing", "with varied instrumentation",
                "with wide stereo field", "with precise stereo imaging"
            ]
            num_descriptors = min(3, max(1, len(prompt.split()) // 2))
            selected_descriptors = random.sample(descriptors, num_descriptors)
            return f"{prompt}, {', '.join(selected_descriptors)}"
        return prompt
        
    def generate_music(self, prompts, duration_sec, **kwargs):
        if isinstance(prompts, str):
            prompts = self.enhance_prompt(prompts)
        elif isinstance(prompts, list):
            prompts = [self.enhance_prompt(p) for p in prompts]

        inputs = self.processor(text=prompts, padding=True, return_tensors="pt").to(self.device)
        gen_params = {**self.default_params, **kwargs}
        tokens_per_generation = 1500
        context_window_duration = self.sliding_window_duration

        with torch.no_grad():
            initial_audio_values = self.model.generate(**inputs, max_new_tokens=tokens_per_generation, **gen_params)
            # For stereo, the shape should be [batch, channels, samples]
            initial_audio = initial_audio_values[0]  # Remove batch dimension, results in [channels, samples]

            if self._detect_high_pitch_issue(initial_audio):
                logger.info("Detected high pitch issue, regenerating with adjusted parameters")
                gen_params["temperature"] *= 1.2
                gen_params["top_k"] -= 50
                gen_params["top_p"] -= 0.05
                gen_params["guidance_scale"] += 1.0
                initial_audio_values = self.model.generate(**inputs, max_new_tokens=tokens_per_generation, **gen_params)
                initial_audio = initial_audio_values[0]

        full_audio = [initial_audio]
        context_window = initial_audio
        target_samples = int(self.sampling_rate * duration_sec)
        
        # For stereo audio, we need to be careful about how we handle the concatenation
        current_samples = full_audio[0].shape[1]  # Get number of samples in the first chunk
        min_overlap_samples = int(self.sampling_rate * 2)

        while current_samples < target_samples:
            # We need to convert to CPU temporarily for the processor
            # This is required by the huggingface processor implementation
            # which expects numpy inputs
            cpu_audio = context_window.cpu().numpy()
            
            # Process audio and get it back to GPU
            context_input = self.processor(
                audio=[cpu_audio], 
                sampling_rate=self.sampling_rate, 
                return_tensors="pt"
            ).to(self.device)
            
            # Merge with text inputs
            merged_inputs = {
                **inputs,
                **{k: v for k, v in context_input.items() if k in ['input_features']}
            }
            
            with torch.no_grad():
                next_audio_values = self.model.generate(
                    **merged_inputs, 
                    max_new_tokens=tokens_per_generation, 
                    **gen_params
                )
                next_audio = next_audio_values[0]  # Remove batch dimension

                if self._detect_high_pitch_issue(next_audio):
                    logger.info("Detected high pitch issue in segment, regenerating")
                    gen_params["temperature"] *= 1.3
                    gen_params["top_k"] -= 75
                    gen_params["top_p"] -= 0.1
                    gen_params["guidance_scale"] += 1.5
                    next_audio_values = self.model.generate(**merged_inputs, max_new_tokens=tokens_per_generation, **gen_params)
                    next_audio = next_audio_values[0]

            overlap_samples = max(min_overlap_samples, int(next_audio.shape[1] * 0.5))
            optimal_overlap_samples = self._find_optimal_splice_point(context_window[:, -overlap_samples*2:], next_audio[:, :overlap_samples*2], overlap_samples)

            crossfaded_audio = self._improved_crossfade(context_window[:, -optimal_overlap_samples:], next_audio, optimal_overlap_samples)
            full_audio.append(crossfaded_audio)
            
            # Update the current total length - for stereo, we use shape[1] which is the time dimension
            current_samples = sum(chunk.shape[1] for chunk in full_audio)
            context_window = next_audio[:, -int(self.sampling_rate * 10):]

        # Concatenate along time dimension (dim=1) for stereo
        full_audio_tensor = torch.cat(full_audio, dim=1)[:, :target_samples]
        full_audio_tensor = self._post_process_audio(full_audio_tensor)
        
        # Only convert to CPU/numpy at the very end
        return full_audio_tensor.cpu().numpy()

    def _find_optimal_splice_point(self, segment1, segment2, window_size):
        if segment1.shape[1] < window_size or segment2.shape[1] < window_size:
            return min(segment1.shape[1], segment2.shape[1], window_size)
        
        # For stereo, we'll analyze both channels and take the average
        correlations = []
        for channel in range(segment1.shape[0]):  # Use actual shape to determine channels
            correlation = torch.nn.functional.conv1d(
                segment1[channel].flip(0).unsqueeze(0).unsqueeze(0), 
                segment2[channel, :window_size].unsqueeze(0).unsqueeze(0)
            ).squeeze()
            correlations.append(correlation)
        
        # Average the correlations from all channels
        avg_correlation = torch.stack(correlations).mean(dim=0)
        max_idx = torch.argmax(torch.abs(avg_correlation)).item()
        optimal_overlap = window_size - abs(max_idx - (window_size - 1))
        return max(optimal_overlap, window_size // 2)

    def _improved_crossfade(self, segment1, segment2, overlap_samples):
        actual_overlap = min(overlap_samples, segment1.shape[1], segment2.shape[1])
        if actual_overlap <= 0:
            return torch.cat([segment1, segment2], dim=1)
        
        # Create fade curves directly on GPU
        t = torch.linspace(0, 1, actual_overlap).to(self.device)
        fade_in = torch.pow(t, 0.5)
        fade_out = torch.pow(1 - t, 0.5)
        
        # For stereo, we need to apply the crossfade to each channel separately
        crossfaded_channels = []
        for channel in range(segment1.shape[0]):  # Use actual shape to determine channels
            # Apply crossfade directly on GPU for this channel
            crossfaded = segment1[channel, -actual_overlap:] * fade_out + segment2[channel, :actual_overlap] * fade_in
            
            # Create the full crossfaded segment for this channel
            full_channel = torch.cat([segment1[channel, :-actual_overlap], crossfaded, segment2[channel, actual_overlap:]])
            crossfaded_channels.append(full_channel)
        
        # Stack channels back together
        return torch.stack(crossfaded_channels)

    def _detect_high_pitch_issue(self, audio_data, threshold=0.65):
        if audio_data is None or audio_data.shape[1] < 1024:
            return False
        
        sample_size = 1024
        max_samples = 5
        channel_results = []
        
        # Determine number of channels from the actual audio tensor
        num_channels = audio_data.shape[0]
        
        for channel in range(num_channels):
            channel_data = audio_data[channel]
            samples = []
            
            if len(channel_data) <= sample_size:
                samples.append(channel_data)
            else:
                for _ in range(min(max_samples, len(channel_data) // sample_size)):
                    max_start = max(0, len(channel_data) - sample_size)
                    start = random.randint(0, max_start)
                    end = min(start + sample_size, len(channel_data))
                    samples.append(channel_data[start:end])
            
            if not samples:
                continue
                
            avg_spectrum = torch.zeros(sample_size // 2, device=self.device)
            for sample in samples:
                if len(sample) < sample_size:
                    padded = torch.nn.functional.pad(sample, (0, sample_size - len(sample)))
                    fft = torch.abs(torch.fft.fft(padded)[:sample_size // 2])
                else:
                    fft = torch.abs(torch.fft.fft(sample[:sample_size])[:sample_size // 2])
                avg_spectrum += fft
            
            avg_spectrum /= len(samples)
            total_energy = torch.sum(avg_spectrum)
            
            if total_energy <= 0:
                continue
                
            avg_spectrum = avg_spectrum / total_energy
            high_freq_energy = torch.sum(avg_spectrum[sample_size // 4:])
            channel_results.append((high_freq_energy / total_energy) > threshold)
        
        # Return True if any channel has high pitch issues
        return any(channel_results) if channel_results else False
    
    def _post_process_audio(self, audio_data):
        audio_data = audio_data.float()
        
        # Process each channel separately
        num_channels = audio_data.shape[0]  # Get actual number of channels
        
        for channel in range(num_channels):
            channel_data = audio_data[channel]
            
            if torch.max(torch.abs(channel_data)) > 0:
                max_val = torch.max(torch.abs(channel_data))
                scale_factor = 0.8 / max_val if max_val > 0 else 1.0
                audio_data[channel] = channel_data * scale_factor
            
            # Check for high pitch issues in this channel
            # Create a temporary tensor with the right shape [channels, samples]
            temp_channel_data = channel_data.unsqueeze(0)  # Add channel dimension
            
            if self._detect_high_pitch_issue(temp_channel_data, threshold=0.55):
                window_size = 3
                filtered_channel = torch.nn.functional.conv1d(
                    channel_data.unsqueeze(0).unsqueeze(0), 
                    torch.ones(1, 1, window_size, device=self.device)/window_size, 
                    padding=1
                ).squeeze()
                audio_data[channel] = filtered_channel
                
        return audio_data
            
    def save_audio(self, audio_data, filename):
        # For stereo, transpose to [samples, channels] format
        audio_data_transposed = audio_data.T
        
        # Ensure audio_data is a NumPy array of int16
        audio_data_int16 = (audio_data_transposed * 32767).astype(np.int16)

        audio = AudioSegment(
            audio_data_int16.tobytes(),
            frame_rate=self.sampling_rate,
            sample_width=2,
            channels=audio_data.shape[0]  # Use actual number of channels
        )
        audio.export(filename, format="mp3")
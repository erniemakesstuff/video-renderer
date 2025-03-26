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
import whisper_timestamped as whisper
import librosa
import librosa.display
import numpy as np
import scipy.signal
import matplotlib.pyplot as plt

logger = logging.getLogger(__name__)


class ContextGenerator(object):
    def __new__(cls):
        if not hasattr(cls, 'instance'):
            cls.instance = super(ContextGenerator, cls).__new__(cls)
        return cls.instance

    def generate(self, sourceVideoFilename, saveAsTranscriptionFilename, saveAsFramesDirectory='.', sourceAudioFilename='.', language = 'en'):
        # TODO https://trello.com/c/HXk5OvEh
        #self.__generate_transcription_file(filename=sourceVideoFilename, saveAsFilename=saveAsTranscriptionFilename, language=language)
        #self.__generate_peaks(filename=sourceVideoFilename)
        self.__analyze_audio_peaks(file_path=sourceVideoFilename)
        pass


    def __generate_transcription_file(self, filename, saveAsFilename, language):
        audio = whisper.load_audio(filename)
        model = whisper.load_model("tiny") # tiny, base, small, medium, large
        results = whisper.transcribe(model, audio, language=language)
        with open(saveAsFilename, "w") as f:
            # Write data to the file
            f.write(json.dumps(results))
    
    def __generate_peaks(self, filename):
            audio_file = AudioFileClip(filename)
            temp_audio_file = str(random.randint(0, 9999)) + "tmp_audio.mp3"
            audio_file.write_audiofile(temp_audio_file)
            y, sr = librosa.load(temp_audio_file)
            # Calculate STFT
            stft = librosa.stft(y)

            # Calculate the RMS energy
            rms = librosa.amplitude_to_db(np.abs(stft), ref=np.max)
            rms = np.mean(rms, axis=0)

            # Find peaks
            peaks, _ = scipy.signal.find_peaks(rms)
            hop_length = 512  # Typical value
            frame_rate = sr / hop_length
            peak_times = peaks / frame_rate

            times = librosa.frames_to_time(np.arange(len(rms)), sr=sr, hop_length=hop_length)

            plt.figure(figsize=(12, 6))
            plt.plot(times, rms, label='RMS Energy')
            plt.plot(peak_times, rms[peaks], 'ro', label='Peaks')
            plt.xlabel('Time (s)')
            plt.ylabel('RMS Energy (dB)')
            plt.title('Audio Peaks Detection')
            plt.legend()
            plt.grid(True)
            plt.show()

            print("Peak Timestamps (seconds):", peak_times)

            os.remove(temp_audio_file)

    def __detect_audio_peaks(self, file_path, top_n=7):
        """
        Detect the top N peaks in an audio file based on amplitude levels.
        
        Parameters:
        -----------
        file_path : str
            Path to the audio file to be analyzed
        top_n : int, optional
            Number of top peaks to return (default is 7)
        
        Returns:
        --------
        tuple: 
            - numpy array of peak timestamps (in seconds)
            - numpy array of corresponding peak amplitudes
        """
        # Load the audio file with explicit dtype
        y, sr = librosa.load(file_path, dtype=np.float32)
        
        # Calculate the RMS (Root Mean Square) energy
        rms_energy = librosa.feature.rms(y=y)[0]
        
        # Normalize the RMS energy
        normalized_energy = (rms_energy - rms_energy.min()) / (rms_energy.max() - rms_energy.min())
        
        # Find peaks using a different approach
        # Use scipy for peak detection
        from scipy.signal import find_peaks
        
        # Find peaks with a minimum prominence
        peaks, _ = find_peaks(normalized_energy, prominence=0.2, width=3)
        
        # If we have more peaks than requested, keep only the top ones
        if len(peaks) > top_n:
            # Get the amplitudes of the peaks
            peak_amplitudes = normalized_energy[peaks]
            
            # Sort peaks by their amplitude
            sorted_peak_indices = np.argsort(peak_amplitudes)[::-1]
            
            # Select the top N peaks
            top_peak_indices = sorted_peak_indices[:top_n]
            peaks = peaks[top_peak_indices]
        
        # Convert peak indices to timestamps
        peak_times = librosa.frames_to_time(peaks, sr=sr)
        peak_amplitudes = normalized_energy[peaks]
        
        # Sort peaks by amplitude in descending order
        sorted_indices = np.argsort(peak_amplitudes)[::-1]
        peak_times = peak_times[sorted_indices]
        peak_amplitudes = peak_amplitudes[sorted_indices]
        
        return peak_times, peak_amplitudes

    # Example usage
    def __analyze_audio_peaks(self, file_path):
        """
        Analyze and print out the top 7 peaks in an audio file.
        
        Parameters:
        -----------
        file_path : str
            Path to the audio file to be analyzed
        """
        try:
            peak_times, peak_amplitudes = self.__detect_audio_peaks(file_path)
            
            print("Top 7 Peak Moments:")
            for i, (time, amplitude) in enumerate(zip(peak_times, peak_amplitudes), 1):
                print(f"{i}. Time: {time:.2f} seconds | Intensity: {amplitude:.4f}")
        
        except Exception as e:
            print(f"Error analyzing audio file: {e}")
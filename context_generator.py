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

    def generate(self, sourceVideoFilename, sourceAudioFilename, saveAsTranscriptionFilename, saveAsFramesDirectory, language):
        # TODO https://trello.com/c/HXk5OvEh
        self.__generate_transcription_file(filename=sourceVideoFilename, language=language)
        self.__generate_peaks(filename=sourceVideoFilename)
        pass


    def __generate_transcription_file(self, filename, saveAsFilename, language):
        audio = whisper.load_audio(filename)
        model = whisper.load_model("tiny") # tiny, base, small, medium, large
        results = whisper.transcribe(model, audio, language=language)
        with open(saveAsFilename, "w") as f:
            # Write data to the file
            f.write(json.dumps(results))
    
    def __generate_peaks(self, filename, saveAsFilename):
            audio_path = 'path/to/your/audio.wav'  # Replace with your audio file path
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
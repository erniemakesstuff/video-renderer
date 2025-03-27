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
import whisper_timestamped as whisper
from transformers import AutoProcessor, MusicgenForConditionalGeneration

logger = logging.getLogger(__name__)

thumbnail_duration = .85
narrator_padding = 3
class RenderClip(object):
    def __init__(self, clip, render_metadata, subtitle_segments = []):
        self.clip = clip
        self.render_metadata = render_metadata
        self.subtitle_segments = subtitle_segments

class MusicScoring(object):
    def __new__(cls):
        if not hasattr(cls, 'instance'):
            cls.instance = super(MusicScoring, cls).__new__(cls)
        return cls.instance

    
    def score_media(self, prompt, sourceMediaID, callbackMediaID) -> bool:
        # 1. Download media.
        # 2. collect noteable times.
        # 3. Generate music.
        # 4. Apply music to final output media; crossfade sfx, etc.
        # 5. Upload to s3 by callbackMediaID.
        pass

    def generate_music(self):
        processor = AutoProcessor.from_pretrained("facebook/musicgen-small")
        model = MusicgenForConditionalGeneration.from_pretrained("facebook/musicgen-small")

        inputs = processor(
            text=["80s pop track with bassy drums and synth", "90s rock song with loud guitars and heavy drums"],
            padding=True,
            return_tensors="pt",
        )

        audio_values = model.generate(**inputs, max_new_tokens=256)

        # save .wav out
        sampling_rate = model.config.audio_encoder.sampling_rate
        scipy.io.wavfile.write("musicgen_out.wav", rate=sampling_rate, data=audio_values[0, 0].numpy())
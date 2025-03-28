import logging
import os
import random
from music_generation import MusicGeneration
from context_generator import ContextGenerator
from s3_wrapper import upload_file, download_file, media_exists

logger = logging.getLogger(__name__)

class MusicScoring(object):
    def __new__(cls):
        if not hasattr(cls, 'instance'):
            cls.instance = super(MusicScoring, cls).__new__(cls)
        return cls.instance
    
    def __init__(self):
        self.music_generator = MusicGeneration()
        self.context_generator = ContextGenerator()
        pass

    
    def score_media(self, prompt, sourceMediaID, callbackMediaID) -> bool:
        if media_exists(callbackMediaID):
            return False
        
        # 1. Download media.
        temp_source_file = str(random.Int(0, 1000)) + "temp_media.mp4"
        download_file(sourceMediaID, temp_source_file)
        # 2. collect noteable times.
        noteable_timestamps_seconds = self.context_generator.get_noteable_timestamps(temp_source_file)
        # 3. Generate music.
        baseline = self.music_generator.generate_music([prompt, 'Slow, rhythmic, background music.'], 200)
        rise = self.music_generator.generate_music([prompt, 'Increasing tension and energy, background music.'], 60)
        climax = self.music_generator.generate_music([prompt, 'Climax, soaring and energetic, climactic, background music.'], 60)
        temp_gen_audio_prefix = str(random.Int(0, 1000)) + "temp_gen_audio_"
        baseline_audio_file = temp_gen_audio_prefix + "baseline.mp3"
        rise_audio_file = temp_gen_audio_prefix + "rise.mp3"
        climax_audio_file = temp_gen_audio_prefix + "climax.mp3"
        self.music_generator.save_audio(baseline_audio_file, baseline)
        self.music_generator.save_audio(rise_audio_file, rise)
        self.music_generator.save_audio(climax_audio_file, climax)
        # 4. Apply music to final output media; crossfade sfx, etc.
        # 5. Upload to s3 by callbackMediaID.


        os.remove(baseline_audio_file)
        os.remove(rise_audio_file)
        os.remove(climax_audio_file)
        pass
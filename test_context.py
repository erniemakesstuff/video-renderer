import datetime
import json
import os
from music_generation import MusicGeneration
from movie_render import MovieRenderer
from context_generator import ContextGenerator
from music_scoring import MusicScoring
os.environ["PATH"] += os.pathsep + r"C:\ffmpeg\bin"  # Adjust path to where you installed FFmpeg
print('start time')
print(datetime.datetime.now())
start_time = datetime.datetime.now()
#inst = context_generator.ContextGenerator()
#inst.get_noteable_timestamps(sourceVideoFilename="/Users/owner/Downloads/testeless-sample-cast.mp4", saveAsTranscriptionFilename="tasteless-transcript.json", language='en')

#gen_inst = MusicGeneration()
#music_prompt = """An epic orchestral masterpiece featuring a powerful symphony of strings, thunderous percussion, heroic brass, and soaring choirs. 
#The music builds with intense crescendos, dynamic contrasts, and a sweeping, cinematic melody, evoking the grandeur of a legendary battle or an awe-inspiring journey. 
#Inspired by Hans Zimmer, Two Steps From Hell, and John Williams."""
#gen_inst.save_audio(gen_inst.generate_music(music_prompt + ' Rhythmic, steady score for an approaching battle.', 200), "terran-base-stereo.mp3")
#gen_inst.save_audio(gen_inst.generate_music(music_prompt + ' Rising tesnion, building suspense to a comming climax. Something momentus is just about to happen!', 60), "terran-rise-stereo.mp3")
#gen_inst.save_audio(gen_inst.generate_music(music_prompt + ' Climactic, finale music signaling a grand crescendo. Exciting and high energy.', 30), "terran-climax-stereo.mp3")

#music_prompt = """A high-energy orchestral battle theme driven by colossal war drums and earth-shaking percussion. 
#Thundering taiko drums, deep cinematic bass hits, and layered percussive textures create an intense heartbeat that propels the music forward.
#Rapid, aggressive staccato strings add tension, while blazing brass fanfares bring heroic power. 
#Explosive crescendos and relentless rhythmic buildups heighten the drama, making the listener feel the weight of an impending battle. 
#Inspired by Ramin Djawadi’s fusion of Western symphonic grandeur and Eastern percussive intensity, blending Hollywood action with ancient war rhythms. 
#Perfect for an epic in-game fight sequence or climactic battle scene."""
#gen_inst.save_audio(gen_inst.generate_music(music_prompt + ' Rhythmic, steady score for an approaching battle.', 20), "prompt-testing-base.mp3")
#gen_inst.save_audio(gen_inst.generate_music(music_prompt + ' Rising tesnion, building suspense to a comming climax. Something momentus is just about to happen!', 20), "prompt-testing-rise-stereo.mp3")
#gen_inst.save_audio(gen_inst.generate_music(music_prompt + ' Climactic, finale music signaling a grand crescendo. Exciting and high energy.', 20), "prompt-testing-climax.mp3")

#sample_prompt = """A dynamic blend of hip-hop and orchestral elements, with sweeping strings and brass, evoking the vibrant energy of the city."""
#gen_inst.save_audio(gen_inst.generate_music(sample_prompt, 30), "beatbox.mp3")
end_time = datetime.datetime.now()
print('start: ' + str(start_time) + ' | end: ' + str(end_time))
print('generated context')

# W/ GPU optimizations

# Input: Small, mono, 200 seconds. Time for generation:  5min.
#TBD
# Input: Small, stereo, 200 seconds. Time for generation: 5min
context_inst = ContextGenerator()
source_file = './Video-tasteless-sample-cast.mp4'#'./tasteless-rush.mp4'
noteable_timestamps_seconds, metadata = context_inst.get_noteable_timestamps(source_file)
print('received metadata: ' + json.dumps(metadata))
#score_inst =  MovieRenderer()
#score_inst.render_video_with_music_scoring(source_file, 'terran-base-battle-stereo.mp3', 'terran-rise-battle-stereo.mp3', 'terran-climax-battle-stereo.mp3', noteable_timestamps_seconds, 'test-render.mp4')


# Retry Scoring
#music_scoring_inst = MusicScoring()
#print('attempting scoring')
#music_scoring_inst.score_media(prompt='wip', sourceMediaID='wip', callbackMediaID='Render-Video-080070a6-e666-4e46-98ee-abffc5276890.mp4')




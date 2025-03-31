import datetime
import json
import os
from music_generation import MusicGeneration
from movie_render import MovieRenderer
from context_generator import ContextGenerator
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

#music_prompt = """A high-energy orchestral battle theme with thunderous percussion, driving rhythms, and powerful brass. 
#The music features intense war drums, fast-paced staccato strings, and soaring melodies, creating an atmosphere of urgency and heroism. 
#Dynamic crescendos and rhythmic buildups enhance the action, making it perfect for an epic in-game fight sequence. Inspired by Two Steps From Hell and Hans Zimmer."""
#gen_inst.save_audio(gen_inst.generate_music(music_prompt + ' Rhythmic, steady score for an approaching battle.', 200), "terran-base-battle-stereo.mp3")
#gen_inst.save_audio(gen_inst.generate_music(music_prompt + ' Rising tesnion, building suspense to a comming climax. Something momentus is just about to happen!', 60), "terran-rise-battle-stereo.mp3")
#gen_inst.save_audio(gen_inst.generate_music(music_prompt + ' Climactic, finale music signaling a grand crescendo. Exciting and high energy.', 30), "terran-climax-battle-stereo.mp3")

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
source_file = './tasteless-rush.mp4'#'./tasteless-rush.mp4'
noteable_timestamps_seconds, metadata = context_inst.get_noteable_timestamps(source_file)
print('received metadata: ' + json.dumps(metadata))
score_inst =  MovieRenderer()
score_inst.render_video_with_music_scoring(source_file, 'terran-base-battle-stereo.mp3', 'terran-rise-battle-stereo.mp3', 'terran-climax-battle-stereo.mp3', noteable_timestamps_seconds, 'test-render.mp4')





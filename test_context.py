import datetime
import os
from music_generation import MusicGeneration
os.environ["PATH"] += os.pathsep + r"C:\ffmpeg\bin"  # Adjust path to where you installed FFmpeg
print('start time')
print(datetime.datetime.now())
start_time = datetime.datetime.now()
#inst = context_generator.ContextGenerator()
#inst.get_noteable_timestamps(sourceVideoFilename="/Users/owner/Downloads/testeless-sample-cast.mp4", saveAsTranscriptionFilename="tasteless-transcript.json", language='en')

gen_inst = MusicGeneration()
music_prompt = """A grand orchestral arrangement with thunderous percussion, epic brass fanfares, and soaring strings, creating a cinematic atmosphere fit for a heroic battle."""
gen_inst.save_audio(gen_inst.generate_music(music_prompt, 200), "terran-medium-base.mp3")
gen_inst.save_audio(gen_inst.generate_music(music_prompt, 60), "terran-medium-rise.mp3")
gen_inst.save_audio(gen_inst.generate_music(music_prompt, 30), "terran-medium-climax.mp3")

#sample_prompt = """A dynamic blend of hip-hop and orchestral elements, with sweeping strings and brass, evoking the vibrant energy of the city."""
#gen_inst.save_audio(gen_inst.generate_music(sample_prompt, 30), "beatbox.mp3")
end_time = datetime.datetime.now()
print('start: ' + str(start_time) + ' | end: ' + str(end_time))
print('generated context')
# TODO: Medium can't load; too biggggg
# 20min: 3 generations 200sec, 60, 30 -- small model, stereo; stereo implementation



import datetime
import movie_render
import context_generator
import music_scoring
print('start time')
print(datetime.datetime.now())
#inst = context_generator.ContextGenerator()
#inst.get_noteable_timestamps(sourceVideoFilename="/Users/owner/Downloads/testeless-sample-cast.mp4", saveAsTranscriptionFilename="tasteless-transcript.json", language='en')

music_score_inst = music_scoring.MusicGeneration()

music_score_inst.save_audio(music_score_inst.generate_music("Progressive rock of the 90's, industrial and heavy.", 200), "terran-base.mp3")
music_score_inst.save_audio(music_score_inst.generate_music("Progressive rock of the 90's, industrial and heavy.", 60), "terran-rise.mp3")
music_score_inst.save_audio(music_score_inst.generate_music("Progressive rock of the 90's, industrial and heavy.", 30), "terran-climax.mp3")
print(datetime.datetime.now())
print('generated context')
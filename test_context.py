import datetime
import movie_render
import context_generator
import music_scoring
print('start time')
print(datetime.datetime.now())
#inst = context_generator.ContextGenerator()
#inst.get_noteable_timestamps(sourceVideoFilename="/Users/owner/Downloads/testeless-sample-cast.mp4", saveAsTranscriptionFilename="tasteless-transcript.json", language='en')

musicScoreInst = music_scoring.MusicScoring()
audio_data = musicScoreInst.generate_music(prompts=["80s pop track with bassy drums and synth", "90s rock song with loud guitars and heavy drums"])
musicScoreInst.save_audio(audio_data=audio_data)
print(datetime.datetime.now())
print('generated context')
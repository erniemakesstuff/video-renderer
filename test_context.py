import movie_render
import context_generator
import music_scoring
print('hello world')
#inst = context_generator.ContextGenerator()
#inst.get_noteable_timestamps(sourceVideoFilename="/Users/owner/Downloads/testeless-sample-cast.mp4", saveAsTranscriptionFilename="tasteless-transcript.json", language='en')

musicScoreInst = music_scoring.MusicScoring()
musicScoreInst.generate_music()
print('generated context')
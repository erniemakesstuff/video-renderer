import movie_render
import context_generator

print('hello world')
inst = context_generator.ContextGenerator()
inst.generate(sourceVideoFilename="/Users/owner/Downloads/testeless-sample-cast.mp4", saveAsTranscriptionFilename="tasteless-transcript.json", language='en')
print('generated context')
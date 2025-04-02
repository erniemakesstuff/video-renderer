import datetime
import json
import os
from music_generation import MusicGeneration
from movie_render import MovieRenderer
from context_generator import ContextGenerator
from consumer import Consumer
os.environ["PATH"] += os.pathsep + r"C:\ffmpeg\bin"  # Adjust path to where you installed FFmpeg
print('local listen: ')
print(datetime.datetime.now())

consumer_inst = Consumer()
consumer_inst.start_poll()





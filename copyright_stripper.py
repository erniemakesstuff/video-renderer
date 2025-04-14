import datetime
import json
import os
from movie_render import MovieRenderer
from s3_wrapper import download_file, upload_file
# TODO: Windows machine.
#os.environ["PATH"] += os.pathsep + r"C:\ffmpeg\bin"  # Adjust path to where you installed FFmpeg
print('start time')
print(datetime.datetime.now())
start_time = datetime.datetime.now()


# S3 File test_video_05142025.mp4
# https://truevine-media-storage.s3.us-west-2.amazonaws.com/test_video_05142025.mp4
str_files_to_process = "test_video_05142025.mp4"
filenames = str_files_to_process.split(",")
render_inst = MovieRenderer()

for f in filenames:
    print('processing: ' + f)
    if '.mp4' not in f:
        continue
    tmp_file = "tmp" + f
    download_success = download_file(f, tmp_file)
    if not download_success:
        print('error downloading file: ' + f)
        break
    
    tmp_store_file = "tmpstore" + f
    render_inst.process_video_new_style(tmp_file, tmp_store_file)
    upload_file(tmp_store_file, f)
    os.remove(tmp_file)
    os.remove(tmp_store_file)


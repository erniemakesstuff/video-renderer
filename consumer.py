import datetime
import time
import traceback
from types import SimpleNamespace
import os
import json
import logging
import sys

import boto3

from botocore.exceptions import ClientError
import multiprocessing
import queue_wrapper
from music_callback import MusicCallbackHandler
from video_editing_callback import VideoEditCallbackHandler

logger = logging.getLogger(__name__)
session = boto3.Session(
    region_name= os.environ['AWS_REGION'],
    aws_access_key_id= os.environ['AWS_ACCESS_KEY_ID'],
    aws_secret_access_key= os.environ['AWS_SECRET_ACCESS_KEY'],
)
sqs = session.client("sqs")
aws_profile = {
    "region_name": os.environ['AWS_REGION'],
    "aws_access_key_id": os.environ['AWS_ACCESS_KEY_ID'],
    "aws_secret_access_key": os.environ['AWS_SECRET_ACCESS_KEY'],
}

media_music_queue = "https://sqs.us-west-2.amazonaws.com/971422718801/media-music-queue"
media_render_queue = "https://sqs.us-west-2.amazonaws.com/971422718801/media-render-queue"

class Consumer:
    def __new__(cls):
        logger.info("created new consumer instance: " + str(os.getpid()))
        if not hasattr(cls, 'instance'):
            cls.instance = super(Consumer, cls).__new__(cls)
        return cls.instance
    

    def start_poll(self, poll_delay_seconds = 20, visibility_timeout_seconds = 420):
        while True:
            try:
                print('polling...' + str(datetime.datetime.now()))
                queue_wrapper.poll(media_render_queue, VideoEditCallbackHandler().handle_message,
                                visibility_timeout_seconds,
                                poll_delay_seconds)
                
                queue_wrapper.poll(media_music_queue, MusicCallbackHandler().handle_message,
                                visibility_timeout_seconds,
                                poll_delay_seconds)
            except Exception as ex:
                print('exception occurred: ' + str(ex))
                logger.info("exception in poller: " + traceback.format_exc())
                time.sleep(60)
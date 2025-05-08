from types import SimpleNamespace
import os
import json
import logging
import sys
from typing import List

import movie_render
import context_generator

import boto3
from botocore.exceptions import ClientError
import s3_wrapper
logger = logging.getLogger(__name__)
class VideoEditCallbackHandler(object):
    def __new__(cls):
        if not hasattr(cls, 'instance'):
             cls.instance = super(VideoEditCallbackHandler, cls).__new__(cls)
        return cls.instance
    
    def __init__(self):
        if not hasattr(self, 'vdeo_editor'):
            self.video_editor = movie_render.MovieRenderer()
        if not hasattr(self, 'context_generator'):
            self.context_generator = context_generator.ContextGenerator()
    
    # Common interface.
    def handle_message(self, mediaEvent) -> bool:
        return self.handle_render(mediaEvent)

    
    def handle_render(self, mediaEvent) -> bool:
        print('received a render message! ' + mediaEvent.ContentLookupKey)
        misc_payload = mediaEvent.MiscJsonPayload
        print('received a render message with values: ')
        print(misc_payload)

        if misc_payload['sinkPresignedS3Url'] != '' or len(misc_payload['sinkPresignedS3Url']) != 0:
            return self.__create_transcript(misc_payload)
        
        return self.__perform_render(self, misc_payload)


    def __perform_render(self, data) -> bool:
        return self.video_editor.perform_render(is_short_form=data["isShortForm"],
                            thumbnail_text=data["thumbnailText"],
                            final_render_sequences=data["finalRenderSequences"],
                            language=data["language"],
                            watermark_text=data["watermarkText"],
                            local_save_as=data["contentLookupKey"],
                            filepath_prefix=data["filepathPrefix"])
    
    def __create_transcript(self, data) -> bool:
        return self.context_generator.transcribe_video_to_cloud(data['sourcePresignedS3Url'], data['sinkPresignedS3Url'])
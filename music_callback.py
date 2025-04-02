from types import SimpleNamespace
import os
import json
import logging
import sys
from typing import List

import boto3
from music_scoring import MusicScoring
from botocore.exceptions import ClientError
import s3_wrapper
logger = logging.getLogger(__name__)
# Final publish blogs, or videos.
class MusicCallbackHandler(object):
    def __new__(cls):
        if not hasattr(cls, 'instance'):
             cls.instance = super(MusicCallbackHandler, cls).__new__(cls)
        return cls.instance
    
    def __init__(self):
        if not hasattr(self, 'music_scoring'):
            self.music_scoring = MusicScoring()
    
    # Common interface.
    def handle_message(self, mediaEvent) -> bool:
        if s3_wrapper.media_exists(mediaEvent.ContentLookupKey):
            return True
        return self.handle_render(mediaEvent)

    
    def handle_render(self, mediaEvent) -> bool:
        return self.handle_music_generation(mediaEvent=mediaEvent)
    
    def handle_music_generation(self, mediaEvent) -> bool:
        return self.music_scoring.score_media(mediaEvent.PromptInstruction,
                                              mediaEvent.ContextSourceUrl,
                                              mediaEvent.ContentLookupKey)
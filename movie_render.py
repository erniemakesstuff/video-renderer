import copy
import math
import multiprocessing
from pathlib import Path
import random
from types import SimpleNamespace
import os
import json
import logging
from typing import List

from botocore.exceptions import ClientError
from moviepy import *
import numpy as np
import whisper_timestamped as whisper

logger = logging.getLogger(__name__)

thumbnail_duration = 0.8

class RenderClip(object):
    def __init__(self, clip, render_metadata, subtitle_segments = []):
        self.clip = clip
        self.render_metadata = render_metadata
        self.subtitle_segments = subtitle_segments

class MovieRenderer(object):
    def __new__(cls):
        if not hasattr(cls, 'instance'):
            cls.instance = super(MovieRenderer, cls).__new__(cls)
        return cls.instance

    
    def perform_render(self, is_short_form, thumbnail_text,
                       final_render_sequences,
                       language,
                       watermark_text,
                       local_save_as,
                       filepath_prefix) -> bool:
        render_sequences = json.loads(final_render_sequences, object_hook=lambda d: SimpleNamespace(**d))
        video_clips = self.__collect_render_clips_by_media_type(render_sequences, 'Video', is_short_form, filepath_prefix, language)
        image_clips = self.__collect_render_clips_by_media_type(render_sequences, 'Image', is_short_form, filepath_prefix, language) # lang=> if we need to overlay text info
        vocal_clips = self.__collect_render_clips_by_media_type(render_sequences, 'Vocal', is_short_form, filepath_prefix, language)
        music_clips = self.__collect_render_clips_by_media_type(render_sequences, 'Music', is_short_form, filepath_prefix, language) # lang=> songs dubbing
        sfx_clips = self.__collect_render_clips_by_media_type(render_sequences, 'Sfx', is_short_form, filepath_prefix, language)
        # TODO: Support text clips
        #text_clips = self.collect_render_clips_by_media_type(render_sequences, 'Text', language)
        visual_layer = self.__create_visual_layer(image_clips=image_clips, 
                                                  video_clips=video_clips, video_title=thumbnail_text, is_short_form=is_short_form)
        audio_layer = self.__create_audio_layer(vocal_clips, music_clips, sfx_clips)
        seconds_narration = self.__get_duration_narration(audio_layer=audio_layer)
        subtitle_layer = self.__get_subtitle_clips(audio_clips=audio_layer, is_short_form=is_short_form)
        duration_watermark = 900
        if seconds_narration > 0:
            duration_watermark = seconds_narration
        watermark_layer = self.__get_watermark_clips(watermark_text=watermark_text, duration=duration_watermark)
        visual_clips = self.__collect_moviepy_clips(visual_layer)
        visual_clips.extend(subtitle_layer)
        visual_clips.extend(watermark_layer)
        composite_video = CompositeVideoClip(np.array(
            visual_clips))
        is_music_video = len(vocal_clips) == 0 and len(music_clips) > 0
        should_mute = is_short_form or is_music_video
        self.__reduce_background_audio(composite_video=composite_video, should_mute=should_mute)
        self.__reduce_background_music(audio_layer=audio_layer, is_music_video=is_music_video)
        audio_layer_clips = self.__collect_moviepy_clips(audio_layer)
        audio_layer_clips.append(composite_video.audio)

        composite_audio = CompositeAudioClip(np.array(
            audio_layer_clips
        ))
        
        composite_video = composite_video.with_audio(composite_audio)
        max_length_short_video_sec = 60
        if not is_music_video and seconds_narration > 0:
            composite_video = composite_video.with_duration(seconds_narration)
        if is_short_form:
            composite_video = composite_video.with_duration(max_length_short_video_sec)
        if is_short_form and seconds_narration > 0:
            duration = min(max_length_short_video_sec, seconds_narration)
            composite_video = composite_video.with_duration(duration)
        aspect_ratio = '16:9'
        if is_short_form:
            aspect_ratio = '9:16'
        # Write local file
        target_save_path = filepath_prefix + local_save_as
        # Moviepy uses the path file extension, mp4, to determine which codec to use.
        codec_save_path = filepath_prefix + local_save_as + ".mp4"
        composite_video.write_videofile(codec_save_path, fps=30, audio=True, audio_codec="aac", ffmpeg_params=['-crf','18', '-aspect', aspect_ratio])
        os.rename(codec_save_path, target_save_path)
        composite_video.close()
        return True
    

    def get_total_duration(clips):
        seconds = 0
        for c in clips:
            seconds += c.duration
        return seconds
    

    def __collect_render_clips_by_media_type(self, final_render_sequences, target_media_type, is_short_form, filepath_prefix, transcriptionLanguage = "en"):
        clips = list()
        width = 1920
        height = 1080
        xc = 960
        yc = 540
        if is_short_form:
            width = 1080
            height = 1920
            xc = 540
            yc = 960
        for s in final_render_sequences:
            if s.MediaType != target_media_type:
                continue
            filename = filepath_prefix + s.ContentLookupKey
            if not Path(filename).is_file():
                raise Exception("missing file: " + filename)
            
            if s.MediaType == 'Vocal':
                subtitle_segments = self.__get_transcribed_text(filename=filename, language=transcriptionLanguage)
                clips.append(RenderClip(clip=AudioFileClip(filename), render_metadata=s, subtitle_segments=subtitle_segments))
            elif s.MediaType == 'Music':
                #return clips
                # TODO dubbing? For music videos.
                clips.append(RenderClip(clip=AudioFileClip(filename), render_metadata=s))
            elif s.MediaType == 'Sfx':
                #return clips
                clips.append(RenderClip(clip=AudioFileClip(filename), render_metadata=s))
            elif s.MediaType == 'Video':
                clips.append(RenderClip(clip=VideoFileClip(filename).cropped(x_center=xc, y_center=yc, height=height, width=width).resized(width=width)
                                        .with_position(("center", "center")), render_metadata=s))
            elif target_media_type == 'Image':
                # TODO overlay text? Probably not.
                clips.append(RenderClip(clip=ImageClip(filename).cropped(x_center=xc, y_center=yc, height=height, width=width).resized(width=width)
                                        .with_position(("center", "center")), render_metadata=s))
            elif target_media_type == 'Text':
                return clips
                # TODO: Need to unpack this first to raw-text, not json.
                #clips.append(RenderClip(clip=TextClip(filename), render_metadata=s))
            else:
                raise Exception('unsupported media type to moviepy clip')

        return clips

    def __reduce_background_audio(self, composite_video, should_mute):
        reduce_to_percent = 0.4
        if should_mute:
            reduce_to_percent = 0 # scale to zero
        composite_video.audio = composite_video.audio.with_volume_scaled(reduce_to_percent)
    
    def __reduce_background_music(self, audio_layer, is_music_video):
        if is_music_video:
            # Keep any background music at 100
            return
        reduce_to_percent = 0.3
        increase_by_percent = 1.70
        for rc in audio_layer:
            if rc.render_metadata.PositionLayer == 'BackgroundMusic':
                rc.clip = rc.clip.with_volume_scaled(reduce_to_percent)
            if rc.render_metadata.PositionLayer == 'Narrator':
                rc.clip = rc.clip.with_volume_scaled(increase_by_percent)
    
    def __get_duration_narration(self, audio_layer):
        seconds = 0
        for rc in audio_layer:
            if rc.render_metadata.PositionLayer == 'Narrator':
                seconds += rc.clip.duration
        return seconds
            
        
    def __create_visual_layer(self, image_clips, video_clips, video_title, is_short_form):
        # TODO: Group and order by PositionLayer + RenderSequence
        # Sequence full-screen content first.
        # Then sequence partials overlaying.
        self.__set_thumbnail_text_rclip(video_title=video_title, visual_clips=image_clips)
        self.__set_image_clips(image_clips=image_clips, duration_sec=2)
        visual_clips = image_clips + video_clips
        self.__combine_sequences(layer_clips=visual_clips)
        if is_short_form:
            self.__increase_color_and_mirror(visual_clips)
        
        # TODO: other position layers.
        # TODO: ensure close all moviepy clips.
        return visual_clips
    
    def __increase_color_and_mirror(self, visual_clips):
        for vc in visual_clips:
            if vc.render_metadata.PositionLayer == 'Thumbnail':
                vc.clip = vc.clip.with_effects([vfx.MultiplyColor(1.1), vfx.LumContrast(0.1, 0.4)])
            else:
                vc.clip = vc.clip.with_effects([vfx.MirrorX(), vfx.MultiplyColor(1.1), vfx.LumContrast(0.1, 0.4)])
        
    
    def __get_random_color(self):
        yellow = "#FFFF00"
        red = "#FF0000"
        lime_green = "#4be506"
        white = "white"
        selected_color = white
        randomNum = random.randint(0, 10)
        if randomNum >= 8:
            selected_color = red
        elif randomNum < 8 and randomNum >= 7:
            selected_color = yellow
        elif randomNum < 7 and randomNum > 4:
            selected_color = lime_green
        elif randomNum <= 4:
            selected_color = white
        return selected_color
        
    
    def __set_thumbnail_text_rclip(self, video_title, visual_clips):
        new_line_word_limit = 4
        words = video_title.split(" ")
        word_count = 1
        formatted_title = ""
        for w in words:
            formatted_title += w
            word_count += 1
            formatted_title += " "
            if word_count % new_line_word_limit == 0:
                formatted_title += "\n"
        words_formatted = formatted_title.split(" ")
        partition_index = math.floor(len(words_formatted) * .70)
        video_title_top = " ".join(words_formatted[:partition_index])
        video_title_bottom = " ".join(words_formatted[partition_index:])
        thumbnail_dur_sec = thumbnail_duration
        secondary_color = self.__get_random_color()
        thumbnail_clip = self.__get_thumbnail_render_clip(visual_clips)
        thumbnail_clip.clip = thumbnail_clip.clip.with_duration(thumbnail_dur_sec)
        thumbnail_text_1 = TextClip(
            font="Impact",
            text=video_title_top,
            font_size=125,
            color="#FFFFFF",
            stroke_color="#000000",
            stroke_width=10,
            margin=(100, 100),
        ).with_position((0.1, 0.2), relative=True).with_duration(thumbnail_dur_sec).with_start(thumbnail_clip.clip.start)
        thumbnail_text_2 = TextClip(
            font="Impact",
            text=video_title_bottom,
            font_size=150,
            stroke_width=10,
            color=secondary_color,
            stroke_color="#000000",
            margin=(100, 100),
        ).with_position((0.1, 0.5), relative=True).with_duration(thumbnail_dur_sec).with_start(thumbnail_clip.clip.start)
        render_meta_copy = copy.copy(thumbnail_clip.render_metadata)
        render_meta_copy.MediaType = 'Text'
        visual_clips.append(RenderClip(clip=thumbnail_text_1, render_metadata=render_meta_copy))
        visual_clips.append(RenderClip(clip=thumbnail_text_2, render_metadata=render_meta_copy))
    
    def __get_thumbnail_render_clip(self, visual_clips):
        for rc in visual_clips:
            if rc.render_metadata.PositionLayer == 'Thumbnail':
                return rc
        
    def __create_audio_layer(self, vocal_clips, music_clips, sfx_clips):
       
        self.__set_start_time_narrator(audio_layer=vocal_clips)
        audio_layer = vocal_clips + sfx_clips
        self.__combine_sequences(audio_layer)
        # contiguous background_music
        self.__combine_sequences(music_clips)
        return audio_layer + music_clips
    
    def __set_start_time_narrator(self, audio_layer):
        for rclip in audio_layer:
            if rclip.render_metadata.RenderSequence == 0 and rclip.render_metadata.MediaType == 'Vocal':
                rclip.clip = rclip.clip.with_start(thumbnail_duration)
                break
    
    def __set_image_clips(self, image_clips, duration_sec):
        for i, ic in enumerate(image_clips):
            if ic.render_metadata.PositionLayer == 'Thumbnail':
                continue
            image_clips[i].clip = image_clips[i].clip.with_duration(duration_sec)
            image_clips[i].clip = image_clips[i].clip.with_position("center", "center")

    def __combine_sequences(self, layer_clips):
        # allocate grouping by sequence numbers
        sequenceNumberToClipsList = {}

        for rclip in layer_clips:
            render_sequence = rclip.render_metadata.RenderSequence
            if render_sequence not in sequenceNumberToClipsList:
                sequenceNumberToClipsList[render_sequence] = []
            
            sequenceNumberToClipsList[render_sequence].append(rclip)
        
        # assign start times
        for i, rclip in enumerate(layer_clips):
            render_sequence = rclip.render_metadata.RenderSequence
            prev_render_sequence = render_sequence - 1
            if prev_render_sequence in sequenceNumberToClipsList:
                clips_in_prev_sequence = sequenceNumberToClipsList[prev_render_sequence]
                max_end_clip = self.__get_longest_render_clip(clips_in_prev_sequence)
                layer_clips[i].clip = rclip.clip.with_start(max_end_clip.clip.end)

    def __get_longest_render_clip(self, clips):
        max_dur_clip = clips[0]
        for rc in clips:
            if rc.clip.duration > max_dur_clip.clip.duration:
                max_dur_clip = rc
        return max_dur_clip
        
    def __collect_moviepy_clips(self, render_clips):
        movie_clips = []
        for r in render_clips:
            movie_clips.append(r.clip)
        return movie_clips
    
    def __get_subtitle_clips(self, audio_clips, is_short_form):
        subtitles = []
        prev_clip_dur = thumbnail_duration # initial offset for thumbnail image.
        for i, ac in enumerate(audio_clips):
            if len(ac.subtitle_segments) > 0:
                text_clips = self.__get_text_clips(text=ac.subtitle_segments, 
                                                   is_short_form=is_short_form,
                                                   offset_sec=prev_clip_dur,
                                                   color=self.__get_random_color())
                subtitles.extend(text_clips)
            prev_clip_dur += ac.clip.duration
        return subtitles
    

    # Ref: https://www.angel1254.com/blog/posts/word-by-word-captions
    # Note: this should be done FIRST for narrator clips to avoid file moviepy clip file locks.
    def __get_transcribed_text(self, filename, language):
        audio = whisper.load_audio(filename)
        model = whisper.load_model("tiny") # tiny, base, small, medium, large
        results = whisper.transcribe(model, audio, language=language)

        return results["segments"]
    
    def __get_text_clips(self, text, is_short_form, offset_sec, color):
        text_clips = []
        position = "bottom"
        if is_short_form:
            position = "center"
        for segment in text:
            for word in segment["words"]:
                clip = TextClip(
                        text=word["text"],
                        font_size=125,
                        stroke_width=5,
                        margin=(100, 100),
                        stroke_color="black", 
                        font="Arial Bold",
                        color=color)
                clip = clip.with_position(("center", position))
                clip = clip.with_start(word["start"] + offset_sec)
                clip = clip.with_end(word["end"] + offset_sec)
                text_clips.append(clip)
        return text_clips
    
    def __get_watermark_clips(self, watermark_text, duration=900):
        clips = []
        water_seg_dur = duration / 4
        clip = TextClip(
            text=watermark_text,
            font="Arial", # OpenType
            color="white",
            font_size = 35,
        ).with_duration(water_seg_dur)
        # x,y offsets
        clips.append(clip.with_position((0.05, 0.95), relative=True).with_start(2)) # bottom left
        clips.append(clip.with_position((0.7, 0.05), relative=True).with_start(water_seg_dur)) # top right
        clips.append(clip.with_position((0.7, 0.95), relative=True).with_start(water_seg_dur * 2)) # bottom right
        clips.append(clip.with_position((0.05, 0.05), relative=True).with_start(water_seg_dur * 3)) # top left
        return clips
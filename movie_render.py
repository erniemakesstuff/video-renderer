import copy
import math
from pathlib import Path
import random
import shutil
from types import SimpleNamespace
import os
import json
import logging
from typing import Any, Dict, List

from botocore.exceptions import ClientError
from moviepy import *
import numpy as np
import whisper_timestamped as whisper
from moviepy.audio.fx import AudioFadeIn, AudioFadeOut
from moviepy.audio.AudioClip import concatenate_audioclips
from s3_wrapper import download_file_via_presigned_url, upload_file_via_presigned_url
import tempfile

logger = logging.getLogger(__name__)

thumbnail_duration = .85
narrator_padding = 3
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
    
    # --- create_subclips method with setsar fix ---
    def create_subclips(
        self,
        presignedSourceS3File: str,
        ratio: str, # "Landscape" or "Portrait"
        cropping: bool, # If True, crop to fill target AR. If False, pad to fit target AR.
        subtitles: bool,
        cuts: List[Dict[str, Any]]
    ):
        """
        Downloads source, creates subclips, applies aspect ratio/subs, uploads.
        Handles aspect ratio conversion correctly, especially with subtitles.
        """
        logger.info(f"Starting subclip creation. Target Ratio: {ratio}, Cropping: {cropping}, Subtitles: {subtitles}, Cuts: {len(cuts)}")

        # Check if whisper is available if subtitles are requested
        if subtitles and whisper is None:
            logger.warning("Subtitles requested, but whisper_timestamped library is not installed. Disabling subtitles.")
            subtitles = False

        source_clip = None
        temp_dir = None
        local_source_path = None
        whisper_segments = None

        try:
            temp_dir = tempfile.mkdtemp(prefix="subclip_")
            logger.info(f"Created temporary directory: {temp_dir}")
            source_suffix = Path(presignedSourceS3File.split('?')[0]).suffix or ".mp4"
            local_source_path = os.path.join(temp_dir, f"source_video{source_suffix}")

            logger.info(f"Downloading source video...")
            if not download_file_via_presigned_url(presignedSourceS3File, local_source_path):
                raise IOError("Failed to download source video.")
            logger.info(f"Source video downloaded to: {local_source_path}")

            if not Path(local_source_path).is_file() or os.path.getsize(local_source_path) == 0:
                raise IOError(f"Downloaded source file is invalid or empty: {local_source_path}")

            logger.info("Loading source video with MoviePy...")
            # Load with target_resolution=None to avoid initial resize if possible
            source_clip = VideoFileClip(local_source_path, audio=True)
            logger.info(f"Source video loaded. Duration: {source_clip.duration:.2f}s, Size: {source_clip.size}")

            # --- Transcription Logic ---
            if subtitles:
                audio_path = os.path.join(temp_dir, "source_audio.aac")
                logger.info("Attempting audio extraction for transcription...")
                try:
                    if source_clip.audio:
                        source_clip.audio.write_audiofile(audio_path, codec='aac', bitrate='192k', logger=None)
                        logger.info(f"Audio extracted to {audio_path}")
                        # Use self reference as create_subclips is part of the class
                        whisper_segments = self.__get_transcribed_text(audio_path, language="en") # Assuming 'en', make configurable
                        if whisper_segments is None:
                            logger.warning("Transcription failed or returned no segments. Subtitles will be skipped for all clips.")
                        else:
                            logger.info(f"Transcription complete. Found {len(whisper_segments)} segments.")
                    else:
                        logger.warning("Source video lacks audio. Cannot generate subtitles.")
                        subtitles = False # Disable permanently if no source audio
                except Exception as audio_ex:
                    logger.error(f"Error during audio extraction/transcription: {audio_ex}", exc_info=True)
                    subtitles = False # Disable permanently on error
                finally:
                    if Path(audio_path).exists():
                        try: os.remove(audio_path)
                        except OSError as e: logger.warning(f"Could not remove temp audio file {audio_path}: {e}")
            # --- End Transcription Logic ---

            # Process each cut
            for i, cut_info in enumerate(cuts):
                start_time = cut_info.get('startTimeSeconds', 0.0)
                end_time = cut_info.get('endTimeSeconds', source_clip.duration)
                upload_url = cut_info.get('presignedS3Url')
                subclip_index = i + 1

                if not upload_url:
                    logger.warning(f"Skipping subclip {subclip_index}: Missing 'presignedS3Url'.")
                    continue

                logger.info(f"Processing subclip {subclip_index}/{len(cuts)}: Time {start_time:.2f}s - {end_time:.2f}s")

                # Validate times
                if start_time < 0: start_time = 0
                if end_time > source_clip.duration:
                    logger.warning(f"Subclip {subclip_index}: end time ({end_time:.2f}s) exceeds source duration ({source_clip.duration:.2f}s). Clamping.")
                    end_time = source_clip.duration
                if start_time >= end_time:
                    logger.warning(f"Skipping subclip {subclip_index}: start time ({start_time:.2f}s) not before end time ({end_time:.2f}s).")
                    continue

                subclip_instance = None
                processed_video_clip = None # Clip potentially resized/cropped by MoviePy
                final_clip_for_render = None
                subtitle_clips_list = []
                local_output_path = os.path.join(temp_dir, f"subclip_{subclip_index}.mp4")
                moviepy_handled_geometry = False

                try:
                    logger.debug(f"Extracting subclip {subclip_index}...")
                    # Using subclipped as requested
                    subclip_instance = source_clip.subclipped(start_time, end_time)

                    w_src, h_src = subclip_instance.size
                    if h_src == 0 or w_src == 0:
                        logger.error(f"Subclip {subclip_index} has zero width or height ({w_src}x{h_src}). Cannot process.")
                        continue
                    src_aspect = w_src / h_src

                    is_target_portrait = ratio.lower() == "portrait"
                    if is_target_portrait:
                        w_target, h_target = 1080, 1920
                        target_aspect_val = 9 / 16
                        target_aspect_str = "9:16"
                    else: # Landscape
                        w_target, h_target = 1920, 1080
                        target_aspect_val = 16 / 9
                        target_aspect_str = "16:9"

                    aspect_tolerance = 0.01
                    aspect_match = abs(src_aspect - target_aspect_val) < aspect_tolerance

                    # Base ffmpeg params (codec, quality, etc.)
                    base_ffmpeg_params = ['-crf', '20', '-preset', 'medium']
                    # This list will hold FFmpeg filter arguments (e.g., ['-vf', 'filter_string'])
                    vf_filter_params = []
                    # This list will hold the actual filter strings (e.g., "scale=...", "setsar=1")
                    vf_filters_list = []

                    # --- Determine Processing Path ---
                    process_with_moviepy_geometry = subtitles

                    if process_with_moviepy_geometry:
                        logger.debug(f"Subclip {subclip_index}: Processing geometry using MoviePy (subtitles enabled).")
                        moviepy_handled_geometry = True # Assume MoviePy will handle it

                        temp_clip = subclip_instance

                        if aspect_match:
                            if w_src != w_target or h_src != h_target:
                                logger.debug(f"Subclip {subclip_index}: AR match, resizing from {w_src}x{h_src} to {w_target}x{h_target}.")
                                processed_video_clip = temp_clip.resized(new_size=(w_target, h_target))
                            else:
                                logger.debug(f"Subclip {subclip_index}: AR and dimensions match. No resize needed.")
                                processed_video_clip = temp_clip
                        else: # Aspect ratios differ
                            if cropping:
                                logger.debug(f"Subclip {subclip_index}: AR mismatch, cropping to {w_target}x{h_target}.")
                                if is_target_portrait: # Crop width
                                    crop_width = h_src * target_aspect_val
                                    logger.debug(f"Applying .cropped(): x_center={w_src/2}, width={crop_width}")
                                    processed_video_clip = temp_clip.cropped(x_center=w_src/2, width=crop_width).resized(new_size=(w_target, h_target))
                                else: # Crop height
                                    crop_height = w_src / target_aspect_val
                                    logger.debug(f"Applying .cropped(): y_center={h_src/2}, height={crop_height}")
                                    processed_video_clip = temp_clip.cropped(y_center=h_src/2, height=crop_height).resized(new_size=(w_target, h_target))
                            else: # Padding
                                logger.debug(f"Subclip {subclip_index}: AR mismatch, padding to {w_target}x{h_target}.")
                                scaled_clip = temp_clip.resized(height=h_target) if temp_clip.aspect_ratio < target_aspect_val else temp_clip.resized(width=w_target)
                                background = ColorClip(size=(w_target, h_target), color=(0,0,0), duration=scaled_clip.duration)
                                processed_video_clip = CompositeVideoClip([background, scaled_clip.with_position("center")], size=(w_target, h_target))

                        # --- Generate and Composite Subtitles ---
                        if whisper_segments:
                           logger.info(f"Generating subtitles for subclip {subclip_index}...")
                           relevant_segments = []
                           subclip_duration_secs = end_time - start_time
                           for seg in whisper_segments:
                               # ... (Segment filtering logic - unchanged) ...
                               seg_start = seg.get('start', 0); seg_end = seg.get('end', 0)
                               if max(start_time, seg_start) < min(end_time, seg_end):
                                   adj_seg = copy.deepcopy(seg)
                                   adj_seg['start'] = max(0, seg_start - start_time)
                                   adj_seg['end'] = min(subclip_duration_secs, seg_end - start_time)
                                   if adj_seg['end'] > adj_seg['start']:
                                       if 'words' in adj_seg:
                                           adj_words = []
                                           for word in seg.get('words', []):
                                               word_start = word.get('start', 0); word_end = word.get('end', 0)
                                               if max(start_time, word_start) < min(end_time, word_end):
                                                    adj_word = copy.deepcopy(word)
                                                    adj_word['start'] = max(0, word_start - start_time)
                                                    adj_word['end'] = min(subclip_duration_secs, word_end - start_time)
                                                    if adj_word['end'] > adj_word['start']: adj_words.append(adj_word)
                                           adj_seg['words'] = adj_words
                                           if not adj_words and not adj_seg.get('text','').strip(): continue
                                       relevant_segments.append(adj_seg)

                           if relevant_segments:
                               # Using the class's own helper method
                               subtitle_clips_list = self._generate_subtitle_text_clips_for_subclip(
                                   segments=relevant_segments, is_short_form=is_target_portrait, offset_sec=0,
                                   clip_width=w_target, clip_height=h_target )
                               logger.info(f"Generated {len(subtitle_clips_list)} TextClips.")

                               if subtitle_clips_list:
                                   all_clips = [processed_video_clip.with_position(("center", "center"))] + subtitle_clips_list
                                   final_clip_for_render = CompositeVideoClip(all_clips, size=(w_target, h_target))
                                   if processed_video_clip.audio:
                                       final_clip_for_render = final_clip_for_render.with_audio(processed_video_clip.audio)
                                   logger.info(f"Composited video and subtitles.")
                               else:
                                    logger.warning(f"Subtitle generation yielded no clips for subclip {subclip_index}. Skipping subtitle overlay.")
                                    final_clip_for_render = processed_video_clip # Use the resized/cropped clip
                           else:
                                logger.info(f"No relevant subtitle segments found for subclip {subclip_index}. Skipping overlay.")
                                final_clip_for_render = processed_video_clip
                        else:
                            logger.warning(f"No transcription data available for subclip {subclip_index}. Skipping subtitle overlay.")
                            final_clip_for_render = processed_video_clip

                        # Even if geometry was handled by MoviePy, we still need setsar for output
                        vf_filters_list.append("setsar=1")

                    else: # Subtitles are OFF - Use FFmpeg for geometry
                        logger.debug(f"Subclip {subclip_index}: Processing geometry using FFmpeg (subtitles disabled).")
                        moviepy_handled_geometry = False
                        final_clip_for_render = subclip_instance

                        # Calculate FFmpeg geometry filters
                        if aspect_match:
                            if w_src != w_target or h_src != h_target:
                                vf_filters_list.append(f"scale={w_target}:{h_target}")
                        else: # AR mismatch
                            if cropping:
                                if is_target_portrait: vf_filters_list.append(f"crop=w=ih*{target_aspect_val}:h=ih,scale={w_target}:{h_target}")
                                else: vf_filters_list.append(f"crop=w=iw:h=iw/{target_aspect_val},scale={w_target}:{h_target}")
                            else: # Pad
                                vf_filters_list.append(f"scale={w_target}:{h_target}:force_original_aspect_ratio=decrease")
                                vf_filters_list.append(f"pad={w_target}:{h_target}:(ow-iw)/2:(oh-ih)/2:black")

                        # Add SAR to the filter list if other filters exist, or create it if needed
                        if vf_filters_list:
                             vf_filters_list.append("setsar=1")
                        else:
                             # Case where AR and size matched perfectly, still need SAR
                             vf_filters_list.append("setsar=1")

                    # --- Assemble vf_filter_params ---
                    # Add the -vf argument ONLY if there are filters in the list
                    if vf_filters_list:
                        vf_filter_params.extend(['-vf', ",".join(vf_filters_list)])

                    # --- Prepare Final FFmpeg Params ---
                    final_ffmpeg_params = list(base_ffmpeg_params) # Copy base
                    final_ffmpeg_params.extend(vf_filter_params)   # Add vf filters (incl setsar)
                    final_ffmpeg_params.extend(['-aspect', target_aspect_str]) # Add aspect ratio hint

                    logger.debug(f"Subclip {subclip_index} - Final FFmpeg Params: {final_ffmpeg_params}")

                    # --- Write Video ---
                    logger.info(f"Writing final subclip {subclip_index} to {local_output_path}...")
                    write_params = {
                        "codec": "libx264",
                        "audio_codec": "aac",
                        "audio_bitrate": "192k",
                        "temp_audiofile": os.path.join(temp_dir, f"temp_audio_{subclip_index}.m4a"),
                        "remove_temp": True,
                        "ffmpeg_params": final_ffmpeg_params, # Use the final calculated params
                        "threads": os.cpu_count(),
                        "logger": 'bar',
                    }

                    # Ensure audio consistency
                    has_audio = final_clip_for_render.audio is not None
                    if not has_audio and subclip_instance.audio is not None:
                         logger.warning(f"Subclip {subclip_index} lost audio; reattaching from original subclip.")
                         final_clip_for_render = final_clip_for_render.with_audio(subclip_instance.audio)
                         has_audio = True
                    elif has_audio and final_clip_for_render is not subclip_instance and final_clip_for_render.audio is None and processed_video_clip and processed_video_clip.audio:
                         logger.warning(f"Subclip {subclip_index} composite lost audio; reattaching from processed clip.")
                         final_clip_for_render = final_clip_for_render.with_audio(processed_video_clip.audio)
                         has_audio = True

                    if not has_audio:
                        logger.warning(f"Subclip {subclip_index} has no audio. Writing video only.")
                        write_params.pop('audio_codec', None)
                        write_params.pop('audio_bitrate', None)
                        write_params.pop('temp_audiofile', None)
                        final_clip_for_render.write_videofile(local_output_path, **write_params, audio=False)
                    else:
                        final_clip_for_render.write_videofile(local_output_path, **write_params, audio=True)

                    logger.info(f"Subclip {subclip_index} written successfully.")

                    # --- Upload ---
                    logger.info(f"Uploading subclip {subclip_index}...")
                    if not upload_file_via_presigned_url(upload_url, local_output_path):
                        logger.error(f"Failed to upload subclip {subclip_index}.")
                    else:
                        logger.info(f"Subclip {subclip_index} uploaded successfully.")

                except Exception as e:
                    logger.error(f"Error processing subclip {subclip_index} ({start_time:.2f}-{end_time:.2f}): {e}", exc_info=True)

                finally:
                    # Cleanup MoviePy objects for this iteration
                    if subclip_instance:
                        try: subclip_instance.close()
                        except Exception: pass
                    if processed_video_clip and processed_video_clip is not subclip_instance:
                         try: processed_video_clip.close()
                         except Exception: pass
                    if (final_clip_for_render and
                        final_clip_for_render is not subclip_instance and
                        final_clip_for_render is not processed_video_clip):
                         try: final_clip_for_render.close()
                         except Exception: pass
                    for tc in subtitle_clips_list:
                        try: tc.close()
                        except Exception: pass
                    if Path(local_output_path).exists():
                        try: os.remove(local_output_path)
                        except OSError as e: logger.warning(f"Could not remove temp output file {local_output_path}: {e}")

        except (IOError, ClientError) as e:
            logger.error(f"A critical error occurred (download/upload/file): {e}", exc_info=True)
            raise
        except Exception as e:
            logger.error(f"An unexpected error occurred during the subclip creation process: {e}", exc_info=True)
            raise
        finally:
            # Final cleanup
            if source_clip:
                try: source_clip.close()
                except Exception: logger.warning("Error closing source clip.")
            if local_source_path and Path(local_source_path).exists():
                try: os.remove(local_source_path)
                except OSError as e: logger.warning(f"Could not remove source file {local_source_path}: {e}")
            if temp_dir and Path(temp_dir).exists():
                try: shutil.rmtree(temp_dir)
                except Exception as e: logger.error(f"Could not remove temporary directory {temp_dir}: {e}")

        logger.info("Subclip creation process finished.")


    # --- Helper: _generate_subtitle_text_clips_for_subclip ---
    # Using the version from the user's provided file which uses 'caption' and seems okay.
    # Respecting the specific TextClip arguments provided by the user.
    def _generate_subtitle_text_clips_for_subclip(self, segments, is_short_form, offset_sec, clip_width, clip_height, color="white", font_size=None, stroke_width=3):
        """Generates MoviePy TextClip objects for subtitles."""
        text_clips = []
        if font_size is None:
            scale_factor = clip_height / 1080 # Scale based on 1080p height
            font_size = int(60 * scale_factor) # Adjust base size (60) as needed

        y_pos_relative = 0.85
        position = ('center', y_pos_relative)
        if is_short_form:
            position = ('center', 'center')
        max_width_prop = 0.90
        target_text_width = int(clip_width * max_width_prop)

        logger.debug(f"Generating text clips. Target size: {clip_width}x{clip_height}, Font size: {font_size}, Position: {position}")

        if not segments: return []

        for segment in segments:
             start_time = segment.get('start', 0) + offset_sec
             end_time = segment.get('end', 0) + offset_sec
             # Using text argument as provided in user's file for TextClip
             text_content = segment.get('text', '').strip().upper() # Consistent casing

             if not text_content or end_time <= start_time: continue

             try:
                # Using arguments as provided in user's file's version of this function
                clip = TextClip(
                        text=text_content,         # Correct keyword 'text'
                        font_size=font_size,       # Correct keyword 'font_size'
                        color=color,             # Correct keyword 'color'
                        stroke_color="black",    # Correct keyword 'stroke_color'
                        stroke_width=stroke_width, # Correct keyword 'stroke_width'
                        font="Impact",           # User provided 'Impact'
                        method='caption',        # User provided 'caption'
                        text_align='center',          # User provided 'align'
                        size=(target_text_width, None) # User provided 'size' with calculated width
                    )
                clip = clip.with_duration(end_time - start_time).with_start(start_time).with_position(position)
                text_clips.append(clip)
             except Exception as e:
                  font_error = "find font" in str(e).lower() or "imagick" in str(e).lower()
                  log_level = logging.ERROR if not font_error else logging.WARNING
                  logger.log(log_level, f"Failed to create TextClip (font issue?={font_error}): '{text_content[:50]}...'. Error: {e}")
                  if font_error:
                      logger.warning("Consider installing 'Impact' font or changing the font in the code.")

        logger.info(f"Generated {len(text_clips)} subtitle text clips.")
        return text_clips
    
    def process_video_new_style(self, input_video_path: str, output_filename: str):
        """
        Processes a video file using the newer MoviePy API style:
        1. Rotates slightly (expanding frame) using with_effects([rotate(...)]).
        2. Increases speed by 2% using with_effects([speedx(...)]).
        3. Adds a semi-transparent text watermark.
        4. Adds thin top/bottom border lines with shifted content.
        5. Saves the output, removing metadata and ensuring a new MD5 hash.
        Assumes 'rotate' and 'speedx' are available in the global namespace.

        Args:
            input_video_path: Path to the source video file.
            output_filename: Path where the processed video will be saved.
        """
        original_clip = None
        final_clip = None

        try:
            logger.info(f"Starting processing for video: {input_video_path} using new MoviePy style.")

            # Load the original video
            original_clip = VideoFileClip(input_video_path)
            logger.debug(f"Loaded clip: duration={original_clip.duration:.2f}s, size={original_clip.size}")

            # 1. Slightly rotate the image by 2 degrees using with_effects()
            #    expand=True increases canvas size to fit the rotated rectangle.
            rotation_angle = 2 # degrees
            # --- CORRECTED: Assuming rotate is available directly ---
            # Ensure 'rotate' is actually defined/imported before this point
            rotated_clip = original_clip.with_effects([
                vfx.Rotate(angle=rotation_angle, expand=True, resample='bilinear')
            ])
            # --- END CORRECTION ---
            w_rot, h_rot = rotated_clip.size # Get dimensions *after* rotation
            logger.debug(f"Applied rotation. New size: {rotated_clip.size}")

            # 2. Increase the video speed by 2% (factor = 1.02)
            #    Using with_effects() method with the assumed 'speedx' function.
            speed_factor = 1.02
            # --- CORRECTED: Assuming speedx is available directly ---
            # Ensure 'speedx' is actually defined/imported before this point
            sped_up_clip = rotated_clip.with_effects([
                vfx.MultiplySpeed(factor=speed_factor),
                vfx.MultiplyColor(1.1),
                vfx.LumContrast(0.1, 0.4)
            ])
            # --- END CORRECTION ---
            new_duration = sped_up_clip.duration # Duration is now shorter
            logger.debug(f"Applied speed change (x{speed_factor}). New duration: {new_duration:.2f}s")


            # 4. Add thin horizontal lines (top/bottom) with shifted content
            line_height = 15
            shift_amount = 30
            top_crop = sped_up_clip.cropped(y1=0, height=line_height, width=w_rot)
            top_line_layer = (top_crop
                            .with_position((shift_amount, 0))
                            .with_duration(new_duration))
            bottom_crop = sped_up_clip.cropped(y1=h_rot - line_height, height=line_height, width=w_rot)
            bottom_line_layer = (bottom_crop
                                .with_position((-shift_amount, h_rot - line_height))
                                .with_duration(new_duration))
            logger.debug("Created shifted top/bottom line layers.")

            # 5. Combine the layers into the final video
            all_clips = []
            watermark_clips = self.__get_watermark_clips("Kherem.com", original_clip.duration)
            all_clips.append(sped_up_clip)
            all_clips.append(top_line_layer)
            all_clips.append(bottom_line_layer)
            all_clips.extend(watermark_clips)
            final_clip = CompositeVideoClip(
                clips=all_clips,
                size=(w_rot, h_rot)
            )
            
            final_clip = final_clip.with_duration(new_duration)
            logger.debug("Composited final video layers.")

            # 6. Write out the final video file
            logger.info(f"Writing final processed video to: {output_filename}")
            final_clip.write_videofile(
                output_filename,
                codec='libx264',
                audio_codec='aac',
                preset='medium',
                ffmpeg_params=["-map_metadata", "-1", "-crf", "20"],
                threads=os.cpu_count(),
                logger='bar',
                temp_audiofile=f'temp-audio-{random.randint(1000,9999)}.m4a',
                remove_temp=True
            )
            logger.info("Video processing completed successfully.")

        except NameError as ne:
            logger.error(f"NameError: {ne}. An effect function (like 'rotate' or 'speedx') might not be available.", exc_info=True)
            logger.error("Ensure 'from moviepy import *' or specific effect imports are used in the calling environment.")
            raise
        except Exception as e:
            logger.error(f"Error during video processing for '{input_video_path}': {e}", exc_info=True)
            raise
        finally:
            # --- Cleanup ---
            logger.debug("Cleaning up video clips...")
            if original_clip:
                try:
                    original_clip.close()
                    logger.debug("Original VideoFileClip closed.")
                except Exception as e_close:
                    logger.warning(f"Exception occurred while closing original_clip: {e_close}")
            logger.debug("Cleanup finished.")

    def render_video_with_music_scoring(self, source_video_file, baseline_audio_file,
                                        rise_audio_file, climax_audio_file, important_moments_seconds, output_filename):
        """output_filename must end w/ .mp4"""
        video_clip = VideoFileClip(source_video_file)
        background_music_layer = self.__create_background_music_scoring(baseline_audio_file, rise_audio_file, climax_audio_file,
                                                                        important_moments_seconds, video_clip.duration)
        background_music_layer.append(video_clip.audio)
        composite_audio = CompositeAudioClip(np.array(
            background_music_layer
        ))
        composite_video = video_clip.with_audio(composite_audio).with_duration(video_clip.duration)
        aspect_ratio = '16:9'
        if composite_video.w < composite_video.h:
            aspect_ratio = '9:16'
    
        composite_video.write_videofile(output_filename, fps=60, audio=True, audio_codec="aac", ffmpeg_params=['-crf','18', '-aspect', aspect_ratio])
        composite_video.close()
        pass

    def __create_background_music_scoring(self, baseline_audio_file, rise_audio_file, climax_audio_file, important_moments_seconds, end_time):
        reduce_to_percent = 0.2
        base_music = AudioFileClip(baseline_audio_file).with_volume_scaled(reduce_to_percent) # 200sec
        rise_music = AudioFileClip(rise_audio_file).with_volume_scaled(reduce_to_percent) # 60 sec
        climax_music = AudioFileClip(climax_audio_file).with_volume_scaled(reduce_to_percent) # 30 sec
        ordered_clips = []
        start_time = 0
        
        for i, cur_timestamp in enumerate(important_moments_seconds):
            if start_time > cur_timestamp:
                continue
            time_to_fill = cur_timestamp - start_time
            num_base_copies = int(time_to_fill // base_music.duration)
            for c in range(num_base_copies):
                ordered_clips.append(base_music.with_start(start_time))
                start_time += base_music.duration
            
            if start_time < cur_timestamp:
                ordered_clips.append(rise_music.with_start(start_time))
                start_time += rise_music.duration
            
            if i % 5 == 0:
                ordered_clips.append(climax_music.with_start(start_time))
                start_time += climax_music.duration

        remaining_time = end_time - start_time
        num_padding = int(remaining_time // base_music.duration)
        for p in range(num_padding):
            ordered_clips.append(base_music.with_start(start_time))
            start_time += base_music.duration

        return self.__crossfade_audio_clips(ordered_clips)
    


    def __crossfade_audio_clips(self, audio_clips, crossfade_duration=3.0):
        """
        Crossfades a list of AudioFileClip objects using MoviePy's audio effects.

        Parameters:
        audio_clips (list): List of AudioFileClip objects.
        crossfade_duration (float): Duration of crossfade in seconds.

        Returns:
        list: A list containing a single AudioClip with crossfades applied.
        """
        if not audio_clips:
            return []

        if len(audio_clips) == 1:
            return audio_clips

        faded_clips = []
        for i in range(len(audio_clips)):
            clip = audio_clips[i]
            if i > 0:
                # Apply fade-out to the end of the previous clip
                faded_clips[-1] = faded_clips[-1].with_effects([AudioFadeOut(duration=crossfade_duration)])

            if i < len(audio_clips) - 1:
                # Apply fade-in to the beginning of the current clip
                clip = clip.with_effects([AudioFadeIn(duration=crossfade_duration)])

            faded_clips.append(clip)

        # Concatenate the faded clips
        final_clip = concatenate_audioclips(faded_clips)

        return [final_clip]

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
        if seconds_narration > narrator_padding:
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
        if not is_music_video and seconds_narration > narrator_padding:
            composite_video = composite_video.with_duration(seconds_narration)
        if is_short_form:
            composite_video = composite_video.with_duration(max_length_short_video_sec)
        if is_short_form and seconds_narration > narrator_padding:
            duration = min(max_length_short_video_sec, seconds_narration)
            composite_video = composite_video.with_duration(duration)
        aspect_ratio = '16:9'
        if is_short_form:
            aspect_ratio = '9:16'
        # Write local file
        target_save_path = filepath_prefix + local_save_as
        # Moviepy uses the path file extension, mp4, to determine which codec to use.
        codec_save_path = filepath_prefix + local_save_as + ".mp4"
        fps = 30
        if is_short_form:
            fps = 60
        composite_video.write_videofile(codec_save_path, fps=fps, audio=True, audio_codec="aac", ffmpeg_params=['-crf','18', '-aspect', aspect_ratio])
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
                clips.append(RenderClip(clip=AudioFileClip(filename), render_metadata=s))
            elif s.MediaType == 'Video':
                clips.append(RenderClip(clip=VideoFileClip(filename).resized(height=height)
                                        .cropped(x_center=xc, y_center=yc, height=height, width=width).resized(width=width)
                                        .with_position(("center", "center")), render_metadata=s))
            elif target_media_type == 'Image':
                # TODO overlay text? Probably not.
                clips.append(RenderClip(clip=ImageClip(filename).resized(height=height)
                                        .cropped(x_center=xc, y_center=yc, height=height, width=width).resized(width=width)
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
        increase_by_percent = 1.7
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
        # Add some padding to avoid abrupt cutoffs; ending.
        return seconds + narrator_padding
            
        
    def __create_visual_layer(self, image_clips, video_clips, video_title, is_short_form):
        # TODO: Group and order by PositionLayer + RenderSequence
        # Sequence full-screen content first.
        # Then sequence partials overlaying.
        self.__set_thumbnail_text_rclip(video_title=video_title, visual_clips=image_clips)
        self.__set_image_clips(image_clips=image_clips, duration_sec=2)
        visual_clips = image_clips + video_clips
        if is_short_form:
            self.__optimize_short_form_vfx(visual_clips)

        self.__combine_sequences(layer_clips=visual_clips)
        
        # TODO: other position layers.
        # TODO: ensure close all moviepy clips.
        return visual_clips
    
    # Optimize short-form for highest retention settings such as brighter, higher contrast colors
    # faster video speeds
    def __optimize_short_form_vfx(self, visual_clips):
        for vc in visual_clips:
            if vc.render_metadata.PositionLayer == 'Thumbnail':
                vc.clip = vc.clip.with_effects([vfx.MultiplyColor(1.1), vfx.LumContrast(0.1, 0.4)])
                continue
            # Ideally, we want each clip to be at most 10-15 seconds.
            speed_multiplier = 1.20
            if vc.clip.duration >= 50:
                speed_multiplier = 6
            elif vc.clip.duration >= 20:
                speed_multiplier = 4

            vc.clip = vc.clip.with_effects([vfx.MirrorX(), vfx.MultiplyColor(1.1), 
                                                vfx.LumContrast(0.1, 0.4), vfx.MultiplySpeed(factor=speed_multiplier)])
        
    
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
            method='caption',
            size=(1000, 1000),
            color="#FFFFFF",
            stroke_color="#000000",
            stroke_width=10,
            margin=(50, 50),
        ).with_position((0.05, 0.2), relative=True).with_duration(thumbnail_dur_sec).with_start(thumbnail_clip.clip.start)
        thumbnail_text_2 = TextClip(
            font="Impact",
            text=video_title_bottom,
            font_size=150,
            method='caption',
            size=(1000, 1000),
            stroke_width=10,
            color=secondary_color,
            stroke_color="#000000",
            margin=(50, 50),
        ).with_position((0.05, 0.5), relative=True).with_duration(thumbnail_dur_sec).with_start(thumbnail_clip.clip.start)
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
        clip_instance = TextClip(
            text=watermark_text,
            font="Arial", # OpenType
            color="white",
            font_size = 35,
        ).with_duration(water_seg_dur)

        start_bl = 2.0
        start_tr = water_seg_dur
        start_br = water_seg_dur * 2
        start_tl = water_seg_dur * 3
        # x,y offsets
        clips.append(clip_instance.with_position(("left", "bottom")).with_start(start_bl))

        # Top right: Align text's right/top to frame's right/top
        clips.append(clip_instance.with_position(("right", "top")).with_start(start_tr))

        # Bottom right: Align text's right/bottom to frame's right/bottom
        clips.append(clip_instance.with_position(("right", "bottom")).with_start(start_br))

        # Top left: Align text's left/top to frame's left/top
        clips.append(clip_instance.with_position(("left", "top")).with_start(start_tl))
        return clips
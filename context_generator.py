import random
import os
import json
import logging
import time

from moviepy import *
import numpy as np
import whisper_timestamped as whisper
import librosa
import librosa.display
import numpy as np
import scipy.signal
import matplotlib.pyplot as plt
from s3_wrapper import upload_file_via_presigned_url, download_file_via_presigned_url

from gemini import GeminiClient

logger = logging.getLogger(__name__)


class ContextGenerator(object):
    def __new__(cls):
        if not hasattr(cls, 'instance'):
            cls.instance = super(ContextGenerator, cls).__new__(cls)
        return cls.instance
    
    def generate(self, sourceVideoFilename, saveAsTranscriptionFilename, saveAsFramesDirectory='.', sourceAudioFilename='.', language = 'en'):
        # TODO https://trello.com/c/HXk5OvEh
        pass


    def transcribe_video_to_cloud(self, sourceRemoteS3Url, sinkRemoteS3Url):
        logger.debug('attempting to transcribe resources: src ' + sourceRemoteS3Url + ' : dest ' + sinkRemoteS3Url)
        local_video_filename = str(random.randint(0, 9999)) + "tmp_video.mp4"
        successful_download = download_file_via_presigned_url(sourceRemoteS3Url, local_video_filename)
        if not successful_download:
            logger.error('failed to download source video file for transcription: ' + sourceRemoteS3Url)
            return False
        transcript_filename = str(random.randint(0, 9999)) + "tmp_transcript.json"
        self.__generate_transcription_file(local_video_filename, transcript_filename, 'en')
        successful_upload = upload_file_via_presigned_url(sinkRemoteS3Url, transcript_filename)
        if not successful_upload:
            logger.error('failed to upload transcription file: ' + sinkRemoteS3Url)
            return False
        
        logger.debug('finished transcribing for ' + sourceRemoteS3Url)
        os.remove(local_video_filename)
        os.remove(transcript_filename)
        return True
    
    def get_noteable_timestamps(self, sourceVideoFilename, saveAsTranscriptionFilename='', saveAsFramesDirectory='.', sourceAudioFilename='.', language = 'en'):
        transcriptSegments = self.__generate_transcription_file(filename=sourceVideoFilename, saveAsFilename=saveAsTranscriptionFilename, language=language)
        noteable_times, metadata = self.__analyze_transcript(transcriptSegments)
        
        peak_audio_times = self.__generate_peaks(filename=sourceVideoFilename)
        joined_times, joined_metadata = self.__left_join_times(peak_audio_times, noteable_times, metadata)

        asc_join_times = sorted(joined_times)
        compacted_times = self.__compact_times(asc_join_times)
        for i in compacted_times:
            print('notable time: ' + str(i))
        
        return compacted_times, joined_metadata

    def __compact_times(self, times):
        if len(times) == 0:
            return times
        compacted_times = []
        compacted_times.append(times[0])
        minute = 60
        for i in times:
            if compacted_times[len(compacted_times) - 1] + minute > i:
                continue
            compacted_times.append(i)

        return compacted_times
    
    def __left_join_times(self, leftTimes, rightTimes, metadata):
        if len(rightTimes) == 0:
            return leftTimes
        join = []
        joined_metadata = []
        metadata_added = {}
        for lt in leftTimes:
            for rt in rightTimes:
                minute = 60
                if lt >= rt - minute or lt <= rt + minute:
                    join.append(lt)
                    break
            for rtm in metadata:
                minute = 60
                isWithinValidTimeframe = lt >= rtm['StartSeconds'] - minute or lt <= rtm['StartSeconds'] + minute
                if isWithinValidTimeframe and rtm['StartSeconds'] not in metadata_added:
                    joined_metadata.append(rtm)
                    metadata_added[rtm['StartSeconds']] = True

        
        return join, joined_metadata

    def __generate_transcription_file(self, filename, saveAsFilename, language):
        audio = whisper.load_audio(filename)
        model = whisper.load_model("tiny") # tiny, base, small, medium, large
        results = whisper.transcribe(model, audio, language=language)
        minified_result = {}
        minified_result['segments'] = []
        minified_result['transcript'] = results['text']
        for i, seg in enumerate(results['segments']):
             segment = {}
             segment['id'] = seg['id']
             segment['text'] = seg['text']
             segment['timestampStartSeconds'] = seg['start']
             segment['timestampEndSeconds'] = seg['end']
             minified_result['segments'].append(segment)
        if len(saveAsFilename) > 0:
            with open(saveAsFilename, "w") as f:
                # Write data to the file
                f.write(json.dumps(minified_result))
        return minified_result
    
    def __analyze_transcript(self, transcriptSegments):
        if len(transcriptSegments['segments']) == 0:
            return []
        segments = transcriptSegments['segments']
        max_slice_size = 100
        # Generate subslices
        analysisAgentClient = GeminiClient()
        notable_timestamps = []
        timestamp_metadata = []
        for start in range(0, len(segments), max_slice_size):
            # Generate subslices for the current chunk
            chunk_end = min(start + max_slice_size, len(segments))
            subslice = segments[start:chunk_end]
            respJsonStr = analysisAgentClient.call_model_json_out(self.__get_analysis_query(), json.dumps(subslice))
            responseData = json.loads(respJsonStr)
            print('gemini response: ' + json.dumps(responseData))
            notable_timestamps += responseData['AllTimestampSeconds']
            timestamp_metadata += responseData['TimestampMetadata']
            print('sleeping...')
            time.sleep(10)

        return notable_timestamps, timestamp_metadata

    def __get_analysis_query(self):
        request = """You are a musical scoring professional. You are able to identify emotional, climactic, and significant moments from media.
        Your goal is to analyze the following transcript for significant moments that should be punctuated in music. Your output will be a json valid array of integers.
        Expected json output:
        {
            "AllTimestampSeconds": int[],
            "TimestampMetadata": [
                {
                    "StartSeconds": int,
                    "Reason": "A reason for the inclusion of this timestamp as a noteable moment. Should include relevant details to justify its inclusion, and provide context."
                },
            ] 
        }
        ###
        """
        return request

    
    def __generate_peaks(self, filename):
        audio_file = AudioFileClip(filename)
        temp_audio_file = str(random.randint(0, 9999)) + "tmp_audio.mp3"
        audio_file.write_audiofile(temp_audio_file)
        y, sr = librosa.load(temp_audio_file)
        # Calculate STFT
        stft = librosa.stft(y)

        # Calculate the RMS energy
        rms = librosa.amplitude_to_db(np.abs(stft), ref=np.max)
        rms = np.mean(rms, axis=0)

        # Find peaks
        peaks, _ = scipy.signal.find_peaks(rms, prominence=0.8, width=20, distance=40)

        top_n = 21
        top_selection = min(len(peaks), top_n)
        # Get the amplitudes of the peaks
        peak_amplitudes = rms[peaks]
        
        # Sort peaks by their amplitude
        sorted_peak_indices = np.argsort(peak_amplitudes)[::-1]
        
        # Select the top N peaks
        top_peak_indices = sorted_peak_indices[:top_selection]
        peaks = peaks[top_peak_indices]

        # Convert peak indices to timestamps
        peak_times = librosa.frames_to_time(peaks, sr=sr)
        peak_amplitudes = rms[peaks]
        
        # Sort peaks by amplitude in descending order
        sorted_indices = np.argsort(peak_amplitudes)[::-1]
        peak_times = peak_times[sorted_indices]
        peak_amplitudes = peak_amplitudes[sorted_indices]

        """for i, (time, amplitude) in enumerate(zip(peak_times, peak_amplitudes), 1):
            print(f"{i}. Time: {time:.2f} seconds | Intensity: {amplitude:.4f}")

        times = librosa.frames_to_time(np.arange(len(rms)), sr=sr, hop_length=512)

        plt.figure(figsize=(20, 10))
        plt.plot(times, rms, label='RMS Energy')
        plt.plot(peak_times, rms[peaks], 'ro', label='Peaks')
        plt.xlabel('Time (s)')
        plt.ylabel('RMS Energy (dB)')
        plt.title('Audio Peaks Detection')
        plt.legend()
        plt.grid(True)
        plt.show()"""

        print("Peak Timestamps (seconds):", peak_times)

        os.remove(temp_audio_file)
        return peak_times
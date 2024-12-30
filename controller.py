from flask import Flask, request
import movie_render
import context_generator
import threading

app = Flask(__name__)

@app.route("/health")
def health_check():
    return "Healthy"


# Accept json body
# isShortForm: boolean
# thumbnailText: string
# finalRenderSequences: string
# language: string
# watermarkText: string
# contentLookupKey: string
# mediaType: string
@app.route("/movie", methods=["POST"])
def create_movie():
    data = request.get_json()  # Get the JSON data from the request
    def render_movie():
        inst = movie_render.MovieRenderer()
        inst.perform_render(is_short_form=data["isShortForm"],
                            thumbnail_text=data["thumbnailText"],
                            final_render_sequences=data["finalRenderSequences"],
                            language=data["language"],
                            watermark_text=data["watermarkText"],
                            local_save_as=data["contentLookupKey"],
                            filepath_prefix=data["filepathPrefix"])
    t1 = threading.Thread(target=render_movie)
    t1.start()
    return "Ok"


# Accept json body
# Create transcription.
# sourceVideoFilename: video filename on shared path.
# sourceAudioFilename: TODO: for audio reactions
# saveAsTranscriptionFilename: collection of text w/ timestamps.
# saveAsPeaksFilename: collection of audio-peaks (excitement zones) w/ timestamps.
# saveAsDirPeakFrames: frames extracted from peaks. Scene filenames defined in saveAsPeaksFilename.
# language
@app.route("/generate-context", methods=["POST"])
def generate_context():
    # TODO https://trello.com/c/HXk5OvEh
    data = request.get_json()  # Get the JSON data from the request
    def generate_context():
        inst = context_generator.ContextGenerator()

    t1 = threading.Thread(target=generate_context)
    t1.start()
    return "Ok"
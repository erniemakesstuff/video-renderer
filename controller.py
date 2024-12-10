from flask import Flask, request
import movie_render
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
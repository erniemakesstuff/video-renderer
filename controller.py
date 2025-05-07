from flask import Flask, jsonify, request, send_file
import movie_render
import context_generator
import threading
from flasgger import Swagger
import logging
from s3_wrapper import generate_presigned_url
app = Flask(__name__)
app.config['SWAGGER'] = {
    'title': 'Video Renderer API',  # Optional: Set a title for your docs
    'uiversion': 3,              # Optional: Use Swagger UI version 3
    # 'openapi': '3.0.2',        # Optional: Specify OpenAPI version
    'specs_route': '/video-renderer/apidocs/' # <<< This is the crucial line
}
swagger = Swagger(app)
log_file = 'app.log'
logging.basicConfig(filename=log_file, level=logging.DEBUG, 
                    format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

@app.route("/video-renderer/health")
def health_check():
    return "Healthy"

@app.route('/video-renderer/')
def index():
  """Index route documentation
  ---
  description: The main page of the API
  responses:
      200:
          description: Successful response
          content:
              application/json:
                  schema:
                      type: object
                      properties:
                          message:
                              type: string
                              description: The response message
  """
  return jsonify({"message": "Hello, Swagger UI!"})

# Accept json body
# isShortForm: boolean
# thumbnailText: string
# finalRenderSequences: string
# language: string
# watermarkText: string
# contentLookupKey: string
# mediaType: string
@app.route("/video-renderer/movie", methods=["POST"])
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
@app.route("/video-renderer/generate-context", methods=["POST"])
def generate_context():
    # TODO https://trello.com/c/HXk5OvEh
    data = request.get_json()  # Get the JSON data from the request
    def generate_context():
        inst = context_generator.ContextGenerator()

    t1 = threading.Thread(target=generate_context)
    t1.start()
    return "Ok"
# Test presigned source: https://truevine-media-storage.s3.us-west-2.amazonaws.com/test_video_05142025.mp4?response-content-disposition=inline&X-Amz-Content-Sha256=UNSIGNED-PAYLOAD&X-Amz-Security-Token=IQoJb3JpZ2luX2VjEIX%2F%2F%2F%2F%2F%2F%2F%2F%2F%2FwEaCXVzLXdlc3QtMiJIMEYCIQDf6HZC2wLkq5GN6wrp3AhGX3Iw2plR225kz8s8yx%2F8EQIhAM8sgLW6BPSgshxr2%2BmgKk7plpN6RHQHHh5gxByGbEkFKrkDCB4QABoMOTcxNDIyNzE4ODAxIgwXsnvWomau5pXoCdgqlgPVMXzmdewrVJWng%2Bp5V9cLVo4VsNsJRVr%2BEzmzE%2BR8%2FRTvAOa%2ByoB2wA2nWyAOiqMC%2FIrt8Pl6X1DckWk3d687hDqH6v5Ell0zL1zVsEzJsszNrI6l8sNWZxqYIzDkVsZPW%2Bu3xJJML96GGRmTafVARHaPCbc8XzldBNWr2BiD5fXsKFGDCOUcGSuPsMOKiuCsTS0UDWks0S%2FFtpc0k2gaXc2oGIJSnZJt9WYxnBwGmmDs%2Fni2IZdkF2vska1ssidqMNJ30QNYdYxOJXRG9rVpKVIe8t1Qo9%2FBgPNkO8ylDzDFi7lP19txHg%2BQPfDYq1XSqbNGlO81sdeRFcmlkHyU1JAF5W2QC5jo%2BGhca9N5BXW%2BmT0xEvS1uuruovftrJLYfql6vvEWz4na3ZUDO2Lv6JSdV%2FTFAeO93AQ5gL75CHsbRZ97K9YPhCF3xlGXhhC7fHBHrOjL0bnQbKL5THHeANtukQkGtK8LWaVjgUwTJ03F8BYNXB5O2gJR4z2jtjeVDdseHxe9xUwvnheOoon6rBOJGfEMMJ7QqsAGOt0CIvMDRIysw24yEeqiyu1WEVKwDI%2F%2FSgDZXmzOPCWghsLDobbOFSlKU%2BWJd9i8lavMreAIRBMhPrAC3g13%2BL2I8J%2B9cNaRV4lDcuAvrbL5d2%2F%2Bz4IKOsCDPd%2FHCj4WmyWixaHSiSAPgZF2eNgISg9MLzdBRKFDOCOoWwGvq3IAu8ZAoYl42hnPUxjpbdBna5u9h8mFKo5flIYWZLpXO%2BYhSuy4rXUnelTNXXdfo%2BwIfSwoct6BNEUH73Xiu7%2BObguKMux6NMCsS5XWgmDnYFhap4pQdi%2Fm8HIPlBOzzBSgtfapMTYsB0nz75zNL8Uwf4Ud4eLaun2omc34Ou%2F6psVzphrsfk994fjvOiSg9YS6y4t%2FJAipZy5Rt0UigLVhW99En34iXNm80bvbun28CYLnDdjzaIGUc9Yk51jgxz8Fr8A0hP%2FYlNw2qZtKDd8%2BKzgY%2BQwI8fjSH2tMBzsDVA%3D%3D&X-Amz-Algorithm=AWS4-HMAC-SHA256&X-Amz-Credential=ASIA6ELKOLNIUNONPXTW%2F20250424%2Fus-west-2%2Fs3%2Faws4_request&X-Amz-Date=20250424T210851Z&X-Amz-Expires=43200&X-Amz-SignedHeaders=host&X-Amz-Signature=3b75ff432cb5ba406245ee082b7b31eb9b5ffe7e173f380ed31b21a34a08fa9e
# Test presigned sink: https://truevine-media-storage.s3.amazonaws.com/test-transcript.json?AWSAccessKeyId=AKIA6ELKOLNI6NHCTNUY&Signature=M9xk8UyJFwvYbOBiamAwdnXBYzU%3D&content-type=application%2Fjson&Expires=1745567113
@app.route("/video-renderer/create-transcription", methods=["POST"])
def create_transcription():
    """Create transcription file from a video using presigned URLs.
    ---
    description: >
        Accepts presigned S3 URLs for a source video and a destination JSON file.
        Initiates an asynchronous transcription process. The source video is downloaded
        using its presigned URL, transcribed, and the resulting JSON transcription data
        is uploaded using the sink presigned URL.

        **Important:** Creating transcriptions is potentially time-consuming.
        This endpoint returns HTTP 200 Ok immediately upon starting the process,
        *not* upon completion. Poll for the existence of the file at the sink location
        (using the object key associated with the sink URL) to determine completion.
        You can monitor progress via the /logs API (if available).

        Manual Presigned URL Generation: https://docs.aws.amazon.com/AmazonS3/latest/userguide/ShareObjectPreSignedURL.html
        Note: generating presigned URLs for "PUT" is separate from the AWS console: https://docs.aws.amazon.com/AmazonS3/latest/userguide/PresignedUrlUploadObject.html
        We assume your sink file already exists, thus calling PUT instead of POST. If your file does not exist, or your presigned URL expects a POST operation, the upload will fail.
        Here is an example of generating a put object request for a json file using python:
                url = s3_client.generate_presigned_url(
                    ClientMethod='put_object',
                    Params={"Bucket": 'truevine-media-storage', "Key": 'test-transcript.json', 'ContentType': 'application/json'},
                    ExpiresIn=36000
                )
    parameters:
      - in: body
        name: body # Or a more descriptive name like 'TranscriptionPayload'
        required: true
        description: JSON object containing the source and sink presigned URLs.
        schema:
          type: object
          properties:
            sourcePresignedS3Url:
              type: string
              description: A valid S3 presigned URL allowing GET access to the source video file (.mp4, etc.).
              example: "https://your-bucket.s3.region.amazonaws.com/videos/input.mp4?AWSAccessKeyId=..."
            sinkPresignedS3Url:
              type: string
              description: A valid S3 presigned URL allowing PUT access for uploading the resulting transcription JSON file.
              example: "https://your-bucket.s3.region.amazonaws.com/transcripts/output.json?AWSAccessKeyId=..."
          required:
            - sourcePresignedS3Url
            - sinkPresignedS3Url

    responses:
      200:
        description: Request accepted, transcription process started asynchronously.
        content:
          application/json:
            schema:
              type: object
              properties:
                message:
                  type: string
                  example: "Ok"
                  description: Confirmation that the process has been initiated.
      400:
        description: Bad Request - Invalid JSON payload or missing required fields.
        # Optional: Add schema for error response
        # content:
        #   application/json:
        #     schema:
        #       type: object
        #       properties:
        #         error:
        #           type: string
    """
    data = request.get_json()  # Get the JSON data from the request
    if not data:
        return {"error": "Request body must be JSON."}, 400
    source_url = data.get('sourcePresignedS3Url')
    sink_url = data.get('sinkPresignedS3Url')

    if not source_url or not sink_url:
        missing = []
        if not source_url: missing.append("sourcePresignedS3Url")
        if not sink_url: missing.append("sinkPresignedS3Url")
        return {"error": f"Missing required fields: {', '.join(missing)}"}, 400
    def generate_context():
        inst = context_generator.ContextGenerator()
        inst.transcribe_video_to_cloud(data['sourcePresignedS3Url'], data['sinkPresignedS3Url'])

    t1 = threading.Thread(target=generate_context, daemon=True)
    t1.start()
    return "Ok"
# Test sink presigned: https://truevine-media-storage.s3.amazonaws.com/test-subclip.mp4?AWSAccessKeyId=AKIA6ELKOLNI6NHCTNUY&Signature=%2FLGS2b0MmCYwVWlXMXoBg%2Fo5jaQ%3D&content-type=video%2Fmp4&Expires=1745575398
@app.route("/video-renderer/video-cut", methods=["POST"])
def create_video_cuts():
    """Create multiple video cuts based on provided parameters.
    ---
    description: >
        Accepts a source video presigned URL, desired output ratio, cropping preference,
        and an array of cut definitions (start/end times and destination presigned URLs).
        Initiates an asynchronous process to download the source video, create each specified
        cut according to the desired ratio and cropping settings, and upload each cut
        to its respective presigned URL.

        **Important:** Video processing can be time-consuming. This endpoint returns
        HTTP 200 Ok immediately upon starting the process, *not* upon completion.
        Poll for the existence of the output files at their respective sink locations
        (using the object keys associated with the presigned URLs) to determine completion.
        Monitor progress via logs if available.

        Manual Presigned URL Generation:
        GET: https://docs.aws.amazon.com/AmazonS3/latest/userguide/ShareObjectPreSignedURL.html
        PUT: https://docs.aws.amazon.com/AmazonS3/latest/userguide/PresignedUrlUploadObject.html

    parameters:
      - name: body
        in: body
        required: true
        description: JSON object defining the source video and the cuts to be made.
        schema:
          type: object
          required:
            - sourceVideoUrl
            - desiredRatio
            - allowCropping
            - enableSubtitles
            - Cuts
          properties:
            sourceVideoUrl:
              type: string
              format: url
              description: A valid S3 presigned URL allowing GET access to the source video file.
              example: "https://your-bucket.s3.region.amazonaws.com/source/my_video.mp4?AWSAccessKeyId=..."
            desiredRatio:
              type: string
              description: The desired aspect ratio for the output cuts.
              enum: ["Portrait", "Landscape"]
              example: "Portrait"
            allowCropping:
              type: boolean
              description: Whether cropping is allowed to achieve the desired aspect ratio. If false, padding might be added.
              example: true
            enableSubtitles:
              type: boolean
              description: When true, adds subtitles to your video per-spoken-word for highest engagement.
              example: true
            Cuts:
              type: array
              description: A list of cuts to be generated from the source video.
              minItems: 1 # Require at least one cut
              items:
                type: object
                required:
                  - presignedS3Url
                  - startTimeSeconds
                  - endTimeSeconds
                properties:
                  presignedS3Url:
                    type: string
                    format: url
                    description: A valid S3 presigned URL allowing PUT access for uploading the resulting video cut.
                    example: "https://your-bucket.s3.region.amazonaws.com/cuts/cut_1.mp4?AWSAccessKeyId=..."
                  startTimeSeconds:
                    type: integer
                    format: int32
                    description: The start time (in seconds) of the cut within the source video.
                    example: 10
                    minimum: 0
                  endTimeSeconds:
                    type: integer
                    format: int32
                    description: The end time (in seconds) of the cut within the source video. Must be greater than startTimeSeconds.
                    example: 25
                    minimum: 0 # Technically should be > startTimeSeconds

    responses:
      200:
        description: Request accepted, video cutting process started asynchronously.
        schema:
          type: object
          properties:
            message:
              type: string
              example: "Ok"
              description: Confirmation that the process has been initiated.
      400:
        description: Bad Request - Invalid JSON payload, missing required fields, or invalid values (e.g., timecodes).
        schema:
          type: object
          properties:
            error:
              type: string
              description: Description of the validation error.
    """
    data = request.get_json()

    # --- Input Validation ---
    if not data:
        app.logger.warning("Received empty request body")
        return jsonify({"error": "Request body must be JSON."}), 400

    required_fields = ["sourceVideoUrl", "desiredRatio", "allowCropping", "Cuts"]
    missing_fields = [field for field in required_fields if field not in data]
    if missing_fields:
        app.logger.warning(f"Request missing fields: {missing_fields}")
        return jsonify({"error": f"Missing required fields: {', '.join(missing_fields)}"}), 400

    source_url = data.get('sourceVideoUrl')
    desired_ratio = data.get('desiredRatio')
    allow_cropping = data.get('allowCropping')
    enable_subtitles = data.get('enableSubtitles')
    cuts_data = data.get('Cuts') # TODO: standardize to camel case.
    if not cuts_data:
        cuts_data = data.get('cuts')

    # Validate types and values
    errors = []
    if not isinstance(source_url, str) or not source_url:
        errors.append("sourceVideoUrl must be a non-empty string.")
    if desired_ratio not in ["Portrait", "Landscape"]:
        errors.append("desiredRatio must be either 'Portrait' or 'Landscape'.")
    if not isinstance(allow_cropping, bool):
        errors.append("allowCropping must be a boolean (true or false).")
    if not isinstance(enable_subtitles, bool):
        errors.append("enableSubtitles must be a boolean (true or false).")
    if not isinstance(cuts_data, list) or not cuts_data:
        errors.append("Cuts must be a non-empty list/array.")
    else:
        for i, cut in enumerate(cuts_data):
            if not isinstance(cut, dict):
                errors.append(f"Item at index {i} in Cuts must be an object.")
                continue # Skip further checks for this item

            cut_required = ["presignedS3Url", "startTimeSeconds", "endTimeSeconds"]
            cut_missing = [f for f in cut_required if f not in cut]
            if cut_missing:
                errors.append(f"Cut at index {i} missing required fields: {', '.join(cut_missing)}.")

            s3_url = cut.get('presignedS3Url')
            start_time = cut.get('startTimeSeconds')
            end_time = cut.get('endTimeSeconds')

            if not isinstance(s3_url, str) or not s3_url:
                 errors.append(f"Cut at index {i}: presignedS3Url must be a non-empty string.")
            if not isinstance(start_time, int) or start_time < 0:
                 errors.append(f"Cut at index {i}: startTimeSeconds must be a non-negative integer.")
            if not isinstance(end_time, int) or end_time < 0:
                 errors.append(f"Cut at index {i}: endTimeSeconds must be a non-negative integer.")
            # Check if times are valid numbers before comparing
            if isinstance(start_time, int) and isinstance(end_time, int) and end_time <= start_time:
                 errors.append(f"Cut at index {i}: endTimeSeconds ({end_time}) must be greater than startTimeSeconds ({start_time}).")

    if errors:
        app.logger.warning(f"Validation errors in request: {errors}")
        # Combine errors into a single message or return list
        return jsonify({"error": "Invalid request payload.", "details": errors}), 400
    # --- End Input Validation ---

    # Define the function to run in a thread (pass validated data)
    def process_video_cuts_async(source, ratio, cropping, subtitles, cuts):
        inst = movie_render.MovieRenderer()
        inst.create_subclips(source, ratio, cropping, subtitles, cuts)

    # Start the background process
    app.logger.info("Request validated. Starting background thread for video cutting.")
    thread_args = (source_url, desired_ratio, allow_cropping, enable_subtitles, cuts_data)
    t1 = threading.Thread(target=process_video_cuts_async, args=thread_args, daemon=True)
    t1.start()

    # Return immediate confirmation
    return jsonify({"message": "Ok"}), 200

@app.route('/video-renderer/logs')
def get_logs():
    """Get logs from the service.
    ---
    description: Log file
    responses:
        200:
            description: Successful response
            content:
                application/json:
                    schema:
                        type: object
                        properties:
                            message:
                                type: string
                                description: The response message
    """
    try:
        generate_presigned_url()
        return send_file(log_file, mimetype='text/plain')
    except FileNotFoundError:
        return "Log file not found", 404
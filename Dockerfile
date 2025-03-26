FROM --platform=linux/amd64 python:3.9-slim-bullseye 

ENV SHARED_MEDIA_VOLUME_PATH="./tmp_media/"
ENV GOOGLE_APPLICATION_CREDENTIALS="./localkey.json"

# Creates an app directory to hold your app’s source code
WORKDIR /app
 
# Copies everything from your root directory into /app
COPY . .
RUN apt-get clean
RUN apt update
RUN apt install ffmpeg -y
RUN apt-get update
RUN apt-get install curl -y curl jq
# --no-cache-dir
RUN pip install --upgrade pip
RUN pip install -r requirements.txt
RUN pip install flask
RUN pip install moviepy --timeout=1000
# Large dependency; will fail on slow connections.
RUN pip install whisper-timestamped --timeout=1000
EXPOSE 8080
EXPOSE 80
EXPOSE 443
ENTRYPOINT ["./startup.sh"]
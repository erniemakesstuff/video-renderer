import requests
import json
# TODO: Revist this, could be useful int he future for image-to-vid, face-swap, etc.
# WIP: Not working...

url = "https://api.goenhance.ai/api/v1/videofaceswap/generate"

payload = json.dumps({
   "args": {
      "reference_img": "https://truevine-media-storage.s3.us-west-2.amazonaws.com/NoraFace.jpg", #https://truevine-media-storage.s3.us-west-2.amazonaws.com/0AFTest.mp4
      "source_img": "https://truevine-media-storage.s3.us-west-2.amazonaws.com/NoraFace.jpg",
      "upscaler": 1,
      "start_time": 0,
      "end_time": 90
   },
   "type": "mx-image-face-swap"
})
headers = {
   'Authorization': 'Bearer sk-rYCfDBn0eQQSk0OwoS_Of0c4GTCICiAAi-ByB4JI1HH7zGfw',
   'Content-Type': 'application/json'
}

response = requests.request("POST", url, headers=headers, data=payload)

print(response.text)
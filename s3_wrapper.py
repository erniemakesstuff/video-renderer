import json
from pathlib import Path
from types import SimpleNamespace
import boto3
import os
import logging
from botocore.exceptions import ClientError
import botocore
import requests
import mimetypes

session = boto3.Session(
    region_name= os.environ['AWS_REGION'],
    aws_access_key_id= os.environ['AWS_ACCESS_KEY_ID'],
    aws_secret_access_key= os.environ['AWS_SECRET_ACCESS_KEY'],
)
logger = logging.getLogger(__name__)
s3_client = session.client('s3')

bucket = "truevine-media-storage"

#S3 Docs: https://boto3.amazonaws.com/v1/documentation/api/latest/guide/s3-uploading-files.html
def upload_file(file_path_name, callbackId) -> bool:
    """Upload a file to an S3 bucket

    :param file_path_name: local path; file to upload
    :param callbackId: S3 object name. Should be MediaEvent callback ID.
    :return: True if file was uploaded, else False
    """
    path_file = Path(file_path_name)
    if not path_file.is_file():
        logger.error("unable to upload to s3 missing local file: " + file_path_name)
        return False
    # Upload the file
    s3_client = boto3.client('s3')
    try:
        response = s3_client.upload_file(file_path_name, bucket, callbackId)
    except ClientError as e:
        logging.error("upload failed for file {0} with error {1}".format(file_path_name, e))
        return False
    return True

def download_file(remote_file_name, save_to_filename) -> bool:
    """Download s3 file
    :param save_to_filename: local path; file to save the contants to
    :param remote_file_name: S3 object name.
    :return: True if file was uploaded, else False
    """
    # Download the remote file
    s3_client = boto3.client('s3')
    try:
        response = s3_client.download_file(bucket, remote_file_name, save_to_filename)
    except ClientError as e:
        logging.error("download failed for file {0} save as {1} with error {2}".format(remote_file_name, save_to_filename, e))
        return False
    return True

def media_exists(remote_file_name) -> bool:
    try:
        s3_client.head_object(Bucket=bucket, Key=remote_file_name)
        return True
    except botocore.exceptions.ClientError as e:
        if e.response['Error']['Code'] == "404":
            return False
    
    return False


def download_file_via_presigned_url(presigned_url: str, save_to_filename: str) -> bool:
    """
    Downloads a file from S3 using a provided presigned GET URL.

    Args:
        presigned_url (str): The presigned URL generated for a GET request.
        save_to_filename (str): The local path where the downloaded file should be saved.

    Returns:
        bool: True if download was successful, False otherwise.
    """
    logger.info(f"Attempting download via presigned URL to {save_to_filename}")
    if not presigned_url:
        logger.error("No presigned URL provided for download.")
        return False

    Path(save_to_filename).parent.mkdir(parents=True, exist_ok=True)

    with requests.get(presigned_url, stream=True) as response:
        response.raise_for_status() # Raise HTTPError for bad responses (4xx or 5xx)
        with open(save_to_filename, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                # If you need filtering/processing of chunks, do it here
                f.write(chunk)
    logger.info(f"Successfully downloaded to {save_to_filename} using presigned URL.")
    return True


def upload_file_via_presigned_url(presigned_url: str, local_file_path: str) -> bool:
    """
    Uploads a local file to S3 using a provided presigned PUT URL.

    Args:
        presigned_url (str): The presigned URL generated for a PUT request.
        local_file_path (str): The path to the local file to upload.

    Returns:
        bool: True if upload was successful, False otherwise.
    """
    logger.info(f"Attempting upload of {local_file_path} via presigned URL")
    if not presigned_url:
        logger.error("No presigned URL provided for upload.")
        return False

    local_file = Path(local_file_path)
    if not local_file.is_file():
        logger.error(f"Local file not found for upload: {local_file_path}")
        return False

    # Guess content type based on filename, default if unknown
    content_type, encoding = mimetypes.guess_type(local_file)
    if content_type is None:
        content_type = 'application/json' # Fallback
    logger.debug(f"Using Content-Type: {content_type} for upload.")

    headers = {'Content-Type': content_type}

    # Read file content and PUT it
    # For very large files, requests might struggle with memory.
    # Consider streaming uploads if needed, though it's more complex with requests' PUT.
    # boto3's managed transfer is better suited for large file uploads.
    with open(local_file, 'rb') as f:
        print('presigned ur: ' + presigned_url)
        print('headers: ')
        print(headers)
        response = requests.put(presigned_url, data=f, headers=headers)
        response.raise_for_status() # Raise HTTPError for bad responses (4xx or 5xx)

    logger.info(f"Successfully uploaded {local_file_path} using presigned URL.")
    return True


def generate_presigned_url():
    try:
        url = s3_client.generate_presigned_url(
            ClientMethod='put_object',
            Params={"Bucket": 'truevine-media-storage', "Key": 'test-subclip-2.mp4', 'ContentType': 'video/mp4'},
            ExpiresIn=36000
        )
    except ClientError:
        raise
    print('created presigned put test: ' + url)
    return url
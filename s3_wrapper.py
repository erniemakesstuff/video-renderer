import json
from pathlib import Path
from types import SimpleNamespace
import boto3
import os
import logging
from botocore.exceptions import ClientError
import botocore
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
import os
import logging
import boto3
from botocore.exceptions import ClientError
from typing import Optional

logger = logging.getLogger(__name__)

def get_s3_client():
    """
    Initializes a boto3 S3 client using environment configurations.
    """
    aws_access_key = os.environ.get("AWS_ACCESS_KEY_ID")
    aws_secret_key = os.environ.get("AWS_SECRET_ACCESS_KEY")
    endpoint_url = os.environ.get("AWS_S3_ENDPOINT_URL")
    
    return boto3.client(
        's3',
        aws_access_key_id=aws_access_key,
        aws_secret_access_key=aws_secret_key,
        endpoint_url=endpoint_url
    )

def generate_upload_signed_url(object_name: str, bucket_name: str = "cineforge-assets", expiration: int = 3600) -> Optional[str]:
    """
    Generates a pre-signed URL to upload a file directly to S3.
    """
    s3_client = get_s3_client()
    try:
        response = s3_client.generate_presigned_url(
            'put_object',
            Params={'Bucket': bucket_name, 'Key': object_name},
            ExpiresIn=expiration
        )
        return response
    except ClientError as e:
        logger.error(f"Failed to generate pre-signed upload URL: {e}")
        return None

def generate_download_signed_url(object_name: str, bucket_name: str = "cineforge-assets", expiration: int = 3600) -> Optional[str]:
    """
    Generates a pre-signed URL to download a file from S3.
    """
    s3_client = get_s3_client()
    try:
        response = s3_client.generate_presigned_url(
            'get_object',
            Params={'Bucket': bucket_name, 'Key': object_name},
            ExpiresIn=expiration
        )
        return response
    except ClientError as e:
        logger.error(f"Failed to generate pre-signed download URL: {e}")
        return None

def upload_file_to_s3(file_path: str, object_name: str, bucket_name: str = "cineforge-assets") -> bool:
    """
    Uploads a local media file directly to S3.
    """
    if not os.path.exists(file_path):
        logger.error(f"Local file {file_path} does not exist for upload.")
        return False
        
    s3_client = get_s3_client()
    try:
        s3_client.upload_file(file_path, bucket_name, object_name)
        logger.info(f"Successfully uploaded {file_path} to S3 bucket {bucket_name} as {object_name}")
        return True
    except ClientError as e:
        logger.error(f"Failed to upload file to S3: {e}")
        return False

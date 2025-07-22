from __future__ import annotations
from urllib.parse import urlparse
import os
from pathlib import Path
from typing import Any
import tempfile
import boto3
from dotenv import load_dotenv
load_dotenv()

S3_TARGET_BUCKET = os.getenv("S3_TARGET_BUCKET")

def get_s3_object_key(s3_uri: str) -> str | None:
    
    parsed = urlparse(s3_uri)
    key = parsed.path.lstrip("/")  # strip leading slash
    return key or None

def get_s3_presigned_url(bucket_name: str, object_key: str):

    s3_client = boto3.client('s3')

    expiration = 3600
    url = s3_client.generate_presigned_url(
        'get_object',
        Params={'Bucket': bucket_name, 'Key': object_key},
        ExpiresIn=expiration
    )

    return url

def upload_fulltext_to_s3( ocr_response: Any, object_key: str, bucket: str = S3_TARGET_BUCKET) -> str:
    """Extracts fulltext markdown from a Mistral OCR response object and uploads it to S3. Returns the s3:// URI of the uploaded file."""

    full_markdown = "\n\n".join(page.markdown for page in ocr_response.pages)
    with tempfile.NamedTemporaryFile(mode="w+", suffix=".md", delete=False) as tmpfile:
        tmpfile.write(full_markdown)
        tmpfile_path = tmpfile.name

    s3_uri = upload_file_to_s3(tmpfile_path, bucket=bucket, object_key=object_key)
    os.remove(tmpfile_path)

    return s3_uri

def upload_file_to_s3(file_path: str | Path, bucket: str = S3_TARGET_BUCKET, object_key: str | None = None) -> str:
    """Upload a file to S3. Returns S3 uri of the uploaded file."""

    print(f"[TRACE] Uploading file to S3: {file_path}")
    file_path = Path(file_path).expanduser().resolve()
    if not file_path.is_file():
        raise FileNotFoundError(file_path)
    if not bucket:
        raise RuntimeError("S3 bucket not specified and S3_TARGET_BUCKET env var not set")

    if object_key is None:
        object_key = f"raw/{file_path.name}"

    s3_client = boto3.client("s3")
    s3_client.upload_file(str(file_path), bucket, object_key)

    return f"s3://{bucket}/{object_key}"
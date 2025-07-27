import os
import requests
import tempfile
from llama_cloud_services import LlamaParse
from distiller.utils.s3_utils import (
    get_s3_object_key,
    get_s3_presigned_url,
)

_S3_TARGET_BUCKET = os.getenv("S3_TARGET_BUCKET")
_LLAMACLOUD_API_KEY = os.environ.get("LLAMACLOUD_API_KEY")
if not _S3_TARGET_BUCKET:
    raise RuntimeError("S3_TARGET_BUCKET must be defined in .env file")
if not _LLAMACLOUD_API_KEY:
    raise RuntimeError("LLAMACLOUD_API_KEY must be defined in .env file")

def extract_text_from_s3(file_s3_uri: str):
    print(f"[TRACE][LLAMA-PARSE] Extracting full text from PDF: {file_s3_uri}")
    object_key = get_s3_object_key(file_s3_uri)
    if not object_key:
        raise ValueError(f"No S3 object key found for {file_s3_uri}")

    s3_presigned_url = get_s3_presigned_url(_S3_TARGET_BUCKET, object_key)

    with tempfile.NamedTemporaryFile(suffix=".pdf") as tmp_file:
        response = requests.get(s3_presigned_url)
        response.raise_for_status()
        tmp_file.write(response.content)
        tmp_file.flush()
        parser = LlamaParse(
            api_key=_LLAMACLOUD_API_KEY,
            result_type="markdown",
            vendor_multimodal_model_name="openai-gpt-4-1-mini"
        )
        result = parser.parse(tmp_file.name)
        full_text = result.get_text()
        return full_text
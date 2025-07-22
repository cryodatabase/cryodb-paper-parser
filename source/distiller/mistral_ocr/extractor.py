import os
from mistralai import Mistral
from psycopg.errors import UniqueViolation
from distiller.postgres_connection import connection_ctx
from distiller.utils.file_utils import generate_md5
from distiller.utils.db_utils import hash_in_psql
from distiller.utils.s3_utils import upload_file_to_s3, upload_fulltext_to_s3, get_s3_object_key, get_s3_presigned_url
from distiller.mistral_ocr.cpa_facts import get_cpa_facts_from_fulltext
from distiller.schemas.papers import Paper, PaperStatus
from datetime import datetime


_S3_TARGET_BUCKET = os.getenv("S3_TARGET_BUCKET")
_MISTRAL_API_KEY = os.environ["MISTRAL_API_KEY"]
if not _S3_TARGET_BUCKET:
    raise RuntimeError("S3_TARGET_BUCKET must be defined in .env file")

if not _MISTRAL_API_KEY:
    raise RuntimeError("MISTRAL_API_KEY must be defined in .env file")

client = Mistral(api_key=_MISTRAL_API_KEY)

def extract_text_from_s3(file_s3_uri: str):
    """Generate OCR for the given file s3 uri(only pdf files) and return the Mistral full text."""
    object_key = get_s3_object_key(file_s3_uri)
    if not object_key:
        raise ValueError(f"No S3 object key found for {file_s3_uri}")

    s3_presigned_url = get_s3_presigned_url(_S3_TARGET_BUCKET, object_key)
    return client.ocr.process(
        model="mistral-ocr-latest",
        document={
            "type": "document_url",
            "document_url": s3_presigned_url,
        },
        include_image_base64=True,
    )

def extract_text_mistral(files: list[str], source_files :str):

    print(f"[TRACE] Extracting full text from PDFs: {files}")
    with connection_ctx() as conn:
        with conn.cursor() as cur:
            for file in files:
                try:
                    file_md5_hash = generate_md5(file)

                    if hash_in_psql(file_md5_hash, cur):
                        print(f"[TRACE] Skipping file {file} as it is already in psql")
                        continue

                    s3_uri = upload_file_to_s3(file, object_key=f"raw/{file_md5_hash}.pdf")
                    fulltext = extract_text_from_s3(s3_uri)
                    fulltext_s3_uri = upload_fulltext_to_s3(fulltext, object_key = f"processed/{file_md5_hash}.txt")
                    
                    paper = Paper(
                        source=source_files,
                        md5_hash=file_md5_hash,
                        file_s3_uri=s3_uri,
                        fulltext_s3_uri=fulltext_s3_uri,
                        file_size_bytes=os.path.getsize(file),
                        status=PaperStatus.DOWNLOADED,
                        created_at=datetime.now(),
                    )

                    cur.execute(
                        """
                        INSERT INTO papers (
                            md5_hash,
                            file_s3_uri,
                            fulltext_s3_uri,
                            file_size_bytes,
                            status,
                            source,
                            created_at
                        )
                        VALUES (%s, %s, %s, %s, %s, %s, %s);
                        """,
                        (
                            paper.md5_hash,
                            paper.file_s3_uri,
                            paper.fulltext_s3_uri,
                            paper.file_size_bytes,
                            paper.status.value,
                            paper.source,
                            paper.created_at,
                        ),
                    )
                    conn.commit()
                    get_cpa_facts_from_fulltext(paper.md5_hash) # this step should be isolated later in order to achieve separation of concerns.
                    
                except UniqueViolation:
                    # Do nothing on duplicate hash, just log and proceed
                    conn.rollback()
                    print(f"[TRACE] Duplicate md5_hash for {file}; skipping insert.")

                except Exception as e:
                    # Roll back any partial work in this iteration and continue with next file
                    conn.rollback()
                    print(f"[ERROR] Failed processing {file}: {e}")

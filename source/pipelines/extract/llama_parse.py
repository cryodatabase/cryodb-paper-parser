from distiller.llama_parse.extractor import extract_text_from_s3
from distiller.utils.file_utils import generate_md5
from distiller.utils.db_utils import hash_in_psql
from distiller.utils.s3_utils import upload_file_to_s3, upload_fulltext_to_s3
from distiller.schemas.papers import Paper, PaperStatus
from distiller.postgres_connection import connection_ctx
from pipelines.utils.paper_utils import add_paper_to_db, update_metadata_from_fulltext, get_cpa_facts_from_fulltext
import os
from datetime import datetime
from typing import Iterator, Tuple

def extract_fulltext(files: list[str], source_files: str) -> Iterator[Tuple[str, str]]:
    print(f"[TRACE][LLAMA-PARSE] Extracting full text from PDFs: {files}")
    with connection_ctx() as conn, conn.cursor() as cur:
        for file in files:
            try:
                file_md5_hash = generate_md5(file)
                if hash_in_psql(file_md5_hash, cur):
                    print(f"[TRACE] Skipping file {file} as it is already in psql")
                    continue
                s3_uri = upload_file_to_s3(file, object_key=f"raw/{file_md5_hash}.pdf")
                fulltext = extract_text_from_s3(s3_uri)
                fulltext_s3_uri = upload_fulltext_to_s3(fulltext, object_key=f"processed/{file_md5_hash}.txt")
                paper = Paper(
                    source=source_files,
                    md5_hash=file_md5_hash,
                    file_s3_uri=s3_uri,
                    fulltext_s3_uri=fulltext_s3_uri,
                    file_size_bytes=os.path.getsize(file),
                    status=PaperStatus.DOWNLOADED,
                    created_at=datetime.now(),
                )
                add_paper_to_db(paper, cur)
                conn.commit()
                yield (file_md5_hash, fulltext)
            except Exception as e:
                conn.rollback()
                print(f"[ERROR] Failed processing {file}: {e}")

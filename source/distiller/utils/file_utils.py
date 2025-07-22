import hashlib
import re

def generate_md5(file_path):
    """Generate MD5 hash of the file's contents."""

    print(f"[TRACE] Generating MD5 hash for file: {file_path}")
    hash_md5 = hashlib.md5()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):   
            hash_md5.update(chunk)
    return hash_md5.hexdigest()

def clean_json_response(text):
    # Remove triple backtick code blocks (with or without 'json')
    cleaned = re.sub(r'^```(?:json)?\s*|\s*```$', '', text.strip(), flags=re.IGNORECASE)
    return cleaned.strip()
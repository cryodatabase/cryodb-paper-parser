def hash_in_psql(file_md5_hash: str, cur) -> bool:

    print(f"[TRACE] Checking if MD5 hash {file_md5_hash} is in psql")
    cur.execute("SELECT 1 FROM papers WHERE md5_hash = %s LIMIT 1;", (file_md5_hash,))
    return cur.fetchone() is not None

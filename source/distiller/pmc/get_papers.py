import os
import requests
import boto3
from dotenv import load_dotenv
load_dotenv()
from time import sleep
from ..postgres_connection import cursor_ctx   # adjust import if path differs

def insert_paper_to_psql(pmid: str, file_s3_uri: str) -> bool:
    """
    Insert a row for this PubMed record, leaving most columns NULL.
    paper_id is stored as 'PMID:{number}', source is fixed to 'PMC'.
    If the row already exists we do nothing.
    """
    paper_id = f"PMID:{pmid}"
    with cursor_ctx(commit=True) as cur:
        # rowcount will be 1 on insert, 0 if skipped due to ON CONFLICT
        cur.execute(
            """
            INSERT INTO papers (paper_id, source, file_s3_uri, is_free_fulltext)
            VALUES (%s, %s, %s, TRUE)
            ON CONFLICT (paper_id) DO NOTHING;
            """,
            (paper_id, "PMC", file_s3_uri),
        )
        return cur.rowcount == 1


# --- Config, default when extracing free full text articles from pubmed central repository ---
PMC_S3_SOURCE_BUCKET = "pmc-oa-opendata"
PMC_S3_XML_FOLDERS = [
    "oa_comm/xml/all",
    "oa_noncomm/xml/all"
]
BATCH_SIZE = 50  # How many PMIDs to map at once; respect NCBI's E-utilities limits

S3_TARGET_BUCKET = os.getenv("S3_TARGET_BUCKET")
if not S3_TARGET_BUCKET:
    raise RuntimeError("S3_TARGET_BUCKET must be defined in .env file")

s3 = boto3.client('s3')

def get_pmcids_for_pmids(pmids):
    # Use NCBI E-utilities esummary to map pmid -> pmcid (works in batches)
    pmid_to_pmcid = {}
    for i in range(0, len(pmids), BATCH_SIZE):
        batch = pmids[i:i+BATCH_SIZE]
        ids = ",".join(batch)
        url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"
        params = {
            "db": "pubmed",
            "id": ids,
            "retmode": "json"
        }
        res = requests.get(url, params=params)
        data = res.json()
        for pmid in batch:
            summary = data['result'].get(pmid)
            if summary:
                # The PMCID is in the articleids list as "pmc"
                pdf_id = None
                for aid in summary.get("articleids", []):
                    if aid.get("idtype") == "pmc" and aid.get("value"):
                        pmcid = aid["value"]
                        # Guarantee format: should be "PMC######"
                        if not pmcid.startswith("PMC"):
                            pmcid = "PMC" + pmcid
                        pmid_to_pmcid[pmid] = pmcid
                        break
        sleep(0.34)  # NCBI recommends max 3 req/sec
    return pmid_to_pmcid

def copy_xml_to_target_bucket(pmcid: str, dest_key: str) -> bool:
    filename = f"{pmcid}.xml"  # dest_key already built by caller
    for folder in PMC_S3_XML_FOLDERS:
        source_key = f"{folder}/{filename}"
        try:
            # Check if file exists
            s3.head_object(Bucket=PMC_S3_SOURCE_BUCKET, Key=source_key)
            # If found, copy to target
            s3.copy(
                {'Bucket': PMC_S3_SOURCE_BUCKET, 'Key': source_key},
                S3_TARGET_BUCKET,
                dest_key
            )
            print(f"Copied PMC XML {pmcid}: {PMC_S3_SOURCE_BUCKET}/{source_key} -> {S3_TARGET_BUCKET}/{dest_key}")
            return True
        except s3.exceptions.ClientError as e:
            if e.response['Error']['Code'] == "404":
                continue
            else:
                print(f"Error for {pmcid}: {e}")
                return False
    print(f"PMC XML for {pmcid} NOT FOUND in PMC Open Access folders.")
    return False

def get_papers_from_pmc(PMIDS_FILE):
    # Read PMIDs as strings (strip any whitespace)
    with open(PMIDS_FILE) as f:
        pmids = [line.strip() for line in f if line.strip().isdigit()]
    print(f"Looking up {len(pmids)} PMIDs...")
    pmid_to_pmcid = get_pmcids_for_pmids(pmids)
    print(f"Found PMCIDs for {len(pmid_to_pmcid)} PMIDs.")
    valid_pairs = pmid_to_pmcid.items()  # only PMIDs with a PMCID
    print(f"Processing {len(valid_pairs)} PMIDs that have a PMC entry...")

    inserted = skipped = 0
    for pmid, pmcid in valid_pairs:
        dest_key = f"raw/{pmcid}.xml"
        file_s3_uri = f"s3://{S3_TARGET_BUCKET}/{dest_key}"
        if insert_paper_to_psql(pmid, file_s3_uri):
            copy_xml_to_target_bucket(pmcid, dest_key)  # copy only on fresh insert
            inserted += 1
        else:
            print(f"Skipped PMDID:{pmid},already present in papers.") 
            skipped += 1
    print(f"Inserted {inserted} new rows into papers.")
    print(f"Skipped {skipped} rows already present in papers.") 


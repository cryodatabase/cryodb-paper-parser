import json
import os
import re
from jsonschema import validate, ValidationError
from dotenv import load_dotenv
import google.generativeai as genai
import sys
from pathlib import Path
load_dotenv()
from distiller.pmc.get_papers import get_papers_from_pmc
from distiller.pmc.get_cpa_facts import get_cpa_facts_from_papers
from distiller.mistral_ocr.extractor import extract_text_mistral    
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if not GEMINI_API_KEY:
    raise RuntimeError("Gemini API key not found in .env file.")

genai.configure(api_key=GEMINI_API_KEY)

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SCHEMA_PATH = os.path.join(SCRIPT_DIR, 'schema.json')
PROMPT_PATH = os.path.join(SCRIPT_DIR, 'gemini_prompt.txt')

print("[TRACE] Loading JSON schema...")
with open(SCHEMA_PATH) as f:
    SCHEMA_OBJ = json.load(f)
    SCHEMA_STR = json.dumps(SCHEMA_OBJ, indent=2)

print("[TRACE] Loading Gemini prompt template...")
with open(PROMPT_PATH) as f:
    PROMPT_TEMPLATE = f.read()

def clean_json_response(text):
    # Remove triple backtick code blocks (with or without 'json')
    cleaned = re.sub(r'^```(?:json)?\s*|\s*```$', '', text.strip(), flags=re.IGNORECASE)
    return cleaned.strip()

def extract_text_from_pdf(pdf_path):
    print(f"[TRACE] Extracting text from PDF: {pdf_path}")
    import pdfplumber
    with pdfplumber.open(pdf_path) as pdf:
        return "\n".join(page.extract_text() or "" for page in pdf.pages)

def extract_paper_data(paper_text):
    print("[TRACE] Preparing prompt for Gemini...")
    prompt = PROMPT_TEMPLATE.replace("{{SCHEMA}}", SCHEMA_STR).replace("{{PAPER_TEXT}}", paper_text)
    print("[TRACE] Sending prompt to Gemini...")
    model = genai.GenerativeModel('gemini-2.5-pro')
    response = model.generate_content(prompt)
    print("[TRACE] Received response from Gemini. Parsing JSON...")
    # Extract the model's response text
    try:
        text = response.text.strip()
        text = clean_json_response(text)
        data = json.loads(text)
        print("[TRACE] Validating response against schema...")
        validate(instance=data, schema=SCHEMA_OBJ)
        print("[TRACE] Validation successful.")
        return data
    except (json.JSONDecodeError, ValidationError) as e:
        print("[ERROR] Error extracting or validating data:", e)
        print("[ERROR] Raw model output:", getattr(response, 'text', str(response)))
        return None

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(f"Usage: python {sys.argv[0]} <paper.txt|paper.pdf>")
        exit(1)
    input_path = sys.argv[1]
    if os.path.isdir(input_path):
        pdf_files = list(Path(input_path).glob("*.pdf"))
        if pdf_files:
            extract_text_mistral(pdf_files, source_files="local_directory")
            exit(0)
        else:
            print(f"No PDF files found in directory '{input_path}'.")
            exit(1)
    if input_path.lower().endswith('pmids.txt'):
        get_papers_from_pmc(input_path)
        get_cpa_facts_from_papers() # max limit 100 papers

    else:
        if input_path.lower().endswith('.pdf'):
            try:
                paper_text = extract_text_from_pdf(input_path)
            except Exception as e:
                print(f"[ERROR] Failed to extract text from PDF: {e}")
                exit(1)
        else:
            print(f"[TRACE] Reading text file: {input_path}")
            with open(input_path) as f:
                paper_text = f.read()

        extracted = extract_paper_data(paper_text)
        if extracted:
            print("[TRACE] Extraction and validation complete. Outputting JSON...")
            print(json.dumps(extracted, indent=2))
        else:
            print("[ERROR] Extraction failed.") 
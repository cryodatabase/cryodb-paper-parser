# CryoRepo Paper Parser

This project analyzes scientific papers and extracts structured data using Gemini (via the `google-generativeai` Python package) and a defined JSON schema.

## Structure

- `source/extractor.py`: Python script to send paper text or PDF to Gemini, extract data, and validate it against the schema.
- `source/schema.json`: JSON schema defining the structure of extracted data.
- `source/gemini_prompt.txt`: Prompt template for Gemini to extract data according to the schema.
- `.env.example`: Example environment file for setting up your Gemini API key.
- `examples/`: Directory for example PDF files.

## Requirements

- Python 3.8+
- [Poetry](https://python-poetry.org/) for dependency management
- Access to Gemini API (API key required)
- `pdfplumber` for PDF text extraction

## Installation

1. **Install Poetry** (if not already installed):
   ```bash
   curl -sSL https://install.python-poetry.org | python3 -
   # You may need to restart your shell or add Poetry to your PATH
   ```

2. **Install dependencies:**
   ```bash
   poetry install
   ```

## Setup

1. Copy the example environment file and add your Gemini API key:
   ```bash
   cp .env.example .env
   # Edit .env and set YOUR_GEMINI_API_KEY
   ```

2. (Optional) Activate the Poetry shell:
   ```bash
   poetry shell
   ```

## Usage

You can now run the extractor with either a text file or a PDF file containing the paper:

```bash
poetry run python source/extractor.py paper.txt
poetry run python source/extractor.py examples/sample.pdf
```

The script will automatically extract text from PDF files using `pdfplumber`.

The script will print the extracted JSON data or an error message if extraction/validation fails.

## Customization

- Edit `source/schema.json` to change the extraction schema.
- Edit `source/gemini_prompt.txt` to tweak the prompt for Gemini.

## Notes

- The `.env` file is ignored by git. Use `.env.example` as a template for sharing setup instructions.
- The project uses the `google-generativeai` package to interact with Gemini, and `python-dotenv` to load environment variables.
- The project uses `pdfplumber` for extracting text from PDF files.
- Place example or test PDFs in the `examples/` directory.

## License

MIT 
cat > README.md <<'EOF'
# OpenWebUI PaddleOCR Backend

FastAPI OCR backend for Open WebUI using PaddleOCR.

This project provides a reusable OCR API for extracting text from images, PDF files, and DOCX documents. It is intended to be used as the backend for an Open WebUI custom OCR tool.

## What This Project Does

The backend accepts an uploaded file, extracts readable text, and returns a structured JSON response.

It supports:

- PNG, JPG, and JPEG image OCR
- PDF text extraction
- OCR fallback for scanned or image-based PDF pages
- DOCX paragraph extraction
- DOCX table extraction
- OCR for images embedded inside DOCX files
- SQLite result caching
- API key authentication
- environment-based configuration
- basic logging and error handling

## Main Use Case

The main use case is an OCR tool inside Open WebUI.

A user uploads a document in Open WebUI. The custom tool sends the file to this backend. The backend extracts the text and returns it to Open WebUI, where the model can use it for summarization, document analysis, citation checking, or other document processing tasks.

## Architecture

```text
Open WebUI
   |
   | Custom OCR tool
   v
FastAPI OCR Backend
   |
   +-- Image extractor
   |      +-- PaddleOCR
   |
   +-- PDF extractor
   |      +-- native PDF text extraction
   |      +-- OCR fallback for scanned pages
   |
   +-- DOCX extractor
   |      +-- native paragraphs
   |      +-- native tables
   |      +-- embedded image OCR
   |
   +-- SQLite cache
```

## Project Structure

```text
app/
  main.py                    FastAPI endpoints
  auth.py                    API key authentication
  cache.py                   SQLite OCR result cache
  config.py                  environment configuration
  schemas.py                 API response models

  services/
    file_service.py          Upload saving and file validation
    ocr_service.py           Cache lookup, routing and response creation

  extractors/
    image_extractor.py       Image validation and OCR
    pdf_extractor.py         PDF native text extraction and OCR fallback
    docx_extractor.py        DOCX text, tables and embedded image OCR

  ocr/
    __init__.py              OCR engine loader
    paddle_engine.py         PaddleOCR integration
    mock_engine.py           Mock OCR engine for development/testing

scripts/
  create_sample_files.py     Generates image, PDF and DOCX test samples

tests/
  test_validation.py

.env.example
requirements.txt
requirements-paddle.txt
README.md
```

## Supported File Types

| File type | Status | Processing |
|---|---:|---|
| PNG | Supported | PaddleOCR |
| JPG/JPEG | Supported | PaddleOCR |
| PDF | Supported | Native text extraction first, OCR fallback if needed |
| DOCX | Supported | Native text/tables + OCR for embedded images |

## Implemented Features

| Feature | Status |
|---|---:|
| FastAPI backend | Done |
| Open WebUI-compatible API | Done |
| API key authentication | Done |
| PNG/JPG/JPEG OCR | Done |
| PDF native text extraction | Done |
| PDF OCR fallback for scanned pages | Done |
| DOCX paragraph extraction | Done |
| DOCX table extraction | Done |
| DOCX embedded image OCR | Done |
| SQLite OCR result cache | Done |
| English and Latvian test samples | Done |
| Structured JSON output | Done |
| Basic logging and error handling | Done |

## How the Backend Works

### Image files

Image files are validated with Pillow to make sure the uploaded file is a real image. Then the image is sent to PaddleOCR.

### PDF files

PDF files are processed page by page.

For each page:

1. The backend first tries native/selectable PDF text extraction.
2. If the page has enough native text, OCR is skipped.
3. If the page has little or no native text, the page is rendered as an image.
4. The rendered image is processed with PaddleOCR.

This makes digital PDFs faster and more accurate, while still supporting scanned PDFs.

### DOCX files

DOCX files are processed in three parts:

1. Native paragraphs are extracted.
2. Native tables are extracted.
3. Embedded images are extracted from the internal `word/media/` folder and processed with OCR.

This allows the backend to read DOCX files that contain both normal editable text and scanned/image content.

### SQLite cache

The backend stores OCR results in SQLite.

The cache key includes:

- file SHA256 hash
- OCR engine
- OCR language
- OCR device
- OCR model settings
- PDF settings

If the same file is uploaded again with the same OCR settings, the backend returns the cached result instead of processing the file again.

## Local Installation

### 1. Clone the repository

```bash
git clone https://github.com/ovaselis/openwebui-paddleocr-backend.git
cd openwebui-paddleocr-backend
```

### 2. Create a Python virtual environment

```bash
python3 -m venv ~/venvs/paddleocr-backend
source ~/venvs/paddleocr-backend/bin/activate
```

### 3. Install dependencies

Install base backend dependencies:

```bash
pip install -r requirements.txt
```

Install PaddleOCR/PaddlePaddle dependencies:

```bash
pip install -r requirements-paddle.txt
```

PaddlePaddle GPU installation can depend on the local CUDA version. CPU installation can be used for basic testing or cloud deployment.

## Environment Configuration

Create `.env` from the example file:

```bash
cp .env.example .env
```

Edit it:

```bash
nano .env
```

Example local GPU configuration:

```env
OCR_API_KEY=change-this-secret

OCR_ENGINE=paddleocr
OCR_LANG=lv
OCR_DEVICE=gpu:0

OCR_DETECTION_MODEL=PP-OCRv5_mobile_det
OCR_RECOGNITION_MODEL=latin_PP-OCRv5_mobile_rec

MAX_FILE_SIZE_MB=10
MAX_PDF_PAGES=0
PDF_DPI=200
PDF_NATIVE_TEXT_FIRST=true
PDF_NATIVE_MIN_CHARS=80

OCR_CACHE_ENABLED=true
OCR_CACHE_PATH=data/cache/ocr_cache.sqlite3

LOG_LEVEL=INFO
```

Important notes:

- `OCR_API_KEY` must be secret.
- `.env` must not be committed to GitHub.
- `MAX_PDF_PAGES=0` means all PDF pages are processed.
- For CPU deployment, use a lower `PDF_DPI` and a positive `MAX_PDF_PAGES` limit.

## Running the Backend Locally

Start the backend:

```bash
source ~/venvs/paddleocr-backend/bin/activate
python -m uvicorn app.main:app --host 0.0.0.0 --port 9713 --env-file .env
```

Health check:

```bash
curl http://127.0.0.1:9713/health
```

Expected response:

```json
{
  "status": "ok",
  "engine": "paddleocr",
  "language": "lv",
  "max_file_size_mb": 10,
  "max_pdf_pages": 0
}
```

## OCR API Usage

Set the API key from `.env`:

```bash
API_KEY=$(grep '^OCR_API_KEY=' .env | cut -d= -f2- | tr -d '\r')
```

Send a file to OCR:

```bash
curl --max-time 600 -X POST "http://127.0.0.1:9713/ocr" \
  -H "X-API-Key: $API_KEY" \
  -F "file=@samples/pdf/latvian_mixed_test.pdf"
```

## API Response Format

Example response:

```json
{
  "filename": "latvian_mixed_test.pdf",
  "file_type": "pdf",
  "engine": "paddleocr",
  "language": "lv",
  "page_count": 2,
  "text": "## Page 1\n\n...",
  "pages": [
    {
      "page": 1,
      "text": "...",
      "confidence": null
    },
    {
      "page": 2,
      "text": "...",
      "confidence": 0.98
    }
  ],
  "warnings": [
    "PDF extraction mode: native text used for 1 page(s), OCR fallback used for 1 page(s)."
  ]
}
```

Response fields:

| Field | Description |
|---|---|
| `filename` | Original uploaded filename |
| `file_type` | `image`, `pdf`, or `docx` |
| `engine` | OCR engine used |
| `language` | Configured OCR language |
| `page_count` | Number of returned pages |
| `text` | Combined page-separated text |
| `pages` | Page-level structured results |
| `confidence` | OCR confidence when available |
| `warnings` | Processing notes, warnings, and cache messages |

## Open WebUI Tool Setup

The backend is designed to be called from an Open WebUI custom tool.

### Local backend URL

If Open WebUI runs inside Docker and this backend runs on the host machine or WSL, use:

```text
http://host.docker.internal:9713/ocr
```

Tool settings:

```text
OCR_API_URL=http://host.docker.internal:9713/ocr
OCR_API_KEY=<same value as backend OCR_API_KEY>
REQUEST_TIMEOUT_SECONDS=300
```

### Azure backend URL

After deploying the backend to Azure, use:

```text
OCR_API_URL=https://<your-azure-backend-domain>/ocr
OCR_API_KEY=<production-secret>
REQUEST_TIMEOUT_SECONDS=300
```

### What the Open WebUI tool should do

The tool should:

1. Accept a user-uploaded file.
2. Send the file to the backend `/ocr` endpoint as multipart form data.
3. Include the `X-API-Key` header.
4. Read the JSON response.
5. Return the extracted `text` field to the chat.

Equivalent curl request:

```bash
curl --max-time 600 -X POST "$OCR_API_URL" \
  -H "X-API-Key: $OCR_API_KEY" \
  -F "file=@document.pdf"
```

### Example Open WebUI prompts

Extract raw text:

```text
Use the OCR tool and return only the extracted text. Do not summarize or translate it.
```

Summarize document:

```text
Use the OCR tool on the uploaded document and summarize the main points in Latvian.
```

Extract references:

```text
Use the OCR tool and extract all references, citations, URLs and page numbers from the document.
```

## Azure Deployment

The recommended first Azure deployment target is Azure Container Apps.

For an Azure Free Trial or CPU deployment, start with conservative settings:

```env
OCR_API_KEY=<production-secret>

OCR_ENGINE=paddleocr
OCR_LANG=lv
OCR_DEVICE=cpu

MAX_FILE_SIZE_MB=10
MAX_PDF_PAGES=10
PDF_DPI=150
PDF_NATIVE_TEXT_FIRST=true
PDF_NATIVE_MIN_CHARS=80

OCR_CACHE_ENABLED=true
OCR_CACHE_PATH=data/cache/ocr_cache.sqlite3

LOG_LEVEL=INFO
```

Digital PDFs and DOCX files should be reasonably fast because native extraction is used where possible. Scanned PDFs and image OCR will be slower on CPU.

### 1. Add a Dockerfile

Create `Dockerfile` in the repository root:

```dockerfile
FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
COPY requirements-paddle.txt .

RUN pip install --no-cache-dir -r requirements.txt
RUN pip install --no-cache-dir -r requirements-paddle.txt

COPY app ./app

EXPOSE 9713

CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "9713"]
```

Depending on PaddleOCR/PaddlePaddle requirements, additional system packages may be needed for a production image.

### 2. Login to Azure

```bash
az login
```

Set subscription if needed:

```bash
az account set --subscription "<subscription-id>"
```

Install or update the Container Apps extension:

```bash
az extension add --name containerapp --upgrade
```

### 3. Create a resource group

```bash
az group create \
  --name rg-openwebui-ocr \
  --location northeurope
```

### 4. Deploy to Azure Container Apps

From the repository root:

```bash
az containerapp up \
  --name openwebui-paddleocr-backend \
  --resource-group rg-openwebui-ocr \
  --location northeurope \
  --source .
```

This builds and deploys the backend as a container app.

### 5. Configure environment variables

After the app is created, configure production environment variables:

```bash
az containerapp update \
  --name openwebui-paddleocr-backend \
  --resource-group rg-openwebui-ocr \
  --set-env-vars \
    OCR_API_KEY="<production-secret>" \
    OCR_ENGINE="paddleocr" \
    OCR_LANG="lv" \
    OCR_DEVICE="cpu" \
    MAX_FILE_SIZE_MB="10" \
    MAX_PDF_PAGES="10" \
    PDF_DPI="150" \
    PDF_NATIVE_TEXT_FIRST="true" \
    PDF_NATIVE_MIN_CHARS="80" \
    OCR_CACHE_ENABLED="true" \
    OCR_CACHE_PATH="data/cache/ocr_cache.sqlite3" \
    LOG_LEVEL="INFO"
```

### 6. Test the deployed backend

Health check:

```bash
curl https://<your-container-app-url>/health
```

OCR test:

```bash
curl --max-time 600 -X POST "https://<your-container-app-url>/ocr" \
  -H "X-API-Key: <production-secret>" \
  -F "file=@samples/pdf/latvian_mixed_test.pdf"
```

### Azure production notes

For a first deployment, SQLite cache inside the container is acceptable for testing.

For production, consider:

- persistent storage for cache
- Azure Files or Blob Storage
- managed database if multiple replicas are used
- stricter file size and page limits
- GPU-capable infrastructure for high-volume scanned document OCR

## Sample Files and Testing

Sample files can be generated with:

```bash
python scripts/create_sample_files.py
```

Generated files:

```text
samples/images/
  english_image_test.png
  latvian_image_test.png
  english_image_test.jpg
  latvian_image_test.jpg

samples/pdf/
  english_mixed_test.pdf
  latvian_mixed_test.pdf

samples/docx/
  english_docx_embedded_image_test.docx
  latvian_docx_embedded_image_test.docx
```

These samples test:

- English OCR
- Latvian OCR
- PNG OCR
- JPG OCR
- PDF native text extraction
- PDF OCR fallback
- DOCX paragraph extraction
- DOCX table extraction
- DOCX embedded image OCR

### Test commands

Image test:

```bash
curl --max-time 600 -X POST "http://127.0.0.1:9713/ocr" \
  -H "X-API-Key: $API_KEY" \
  -F "file=@samples/images/latvian_image_test.png"
```

PDF test:

```bash
curl --max-time 600 -X POST "http://127.0.0.1:9713/ocr" \
  -H "X-API-Key: $API_KEY" \
  -F "file=@samples/pdf/latvian_mixed_test.pdf"
```

DOCX test:

```bash
curl --max-time 600 -X POST "http://127.0.0.1:9713/ocr" \
  -H "X-API-Key: $API_KEY" \
  -F "file=@samples/docx/latvian_docx_embedded_image_test.docx"
```

## Functional Requirements Coverage

| Requirement | Status | Implementation |
|---|---:|---|
| FR-1 Open WebUI Integration | Done | Open WebUI custom tool can call the FastAPI backend. |
| FR-2 OCR Input Support | Done | PNG, JPG and JPEG image OCR are supported. |
| FR-3 PDF Support | Done | PDFs support native text extraction and OCR fallback. |
| FR-4 OCR Backend Connection | Done | `/ocr` endpoint accepts files and returns OCR results. |
| FR-5 Text Extraction Output | Done | Extracted text is returned in readable page-separated format. |
| FR-6 Structured Output | Done | JSON includes filename, file type, pages, confidence, text and warnings. |
| FR-7 File Validation | Done | Unsupported extensions and invalid files are rejected. |
| FR-8 Error Handling | Done | Clear HTTP errors and warnings are returned. |
| FR-9 Environment Configuration | Done | `.env` and `.env.example` configure API key, OCR, PDF and cache settings. |
| FR-10 Logging | Done | Backend logs startup, requests, cache behavior and processing errors. |

## Error Handling

The backend handles:

- missing or invalid API key
- unsupported file types
- files exceeding size limit
- invalid or corrupted images
- invalid or corrupted PDFs
- invalid or corrupted DOCX files
- unexpected OCR processing errors

Example unsupported file response:

```json
{
  "detail": "Unsupported file type '.txt'. Supported: ['.docx', '.jpeg', '.jpg', '.pdf', '.png']"
}
```

## Security Notes

Implemented security measures:

- API key authentication through `X-API-Key`
- `.env` excluded from Git
- file extension validation
- file size limit
- temporary upload cleanup
- structured error handling
- SQLite cache stored locally

Production recommendations:

- use HTTPS
- keep API keys secret
- rotate secrets when needed
- protect cache storage because it contains extracted text
- do not expose the backend publicly without authentication
- use conservative file size, PDF page and DPI limits
- review dependency licenses before production use

## Cache Management

Clear local SQLite cache:

```bash
rm -f data/cache/ocr_cache.sqlite3
```

Or clear rows:

```bash
sqlite3 data/cache/ocr_cache.sqlite3 "DELETE FROM ocr_cache;"
```

A repeated request should show this warning when cache is used:

```text
Returned cached OCR result; file was not processed again.
```

## Demo Evidence Checklist

Recommended evidence for final submission:

- GitHub repository screenshot
- `/health` endpoint screenshot
- image OCR test screenshot
- PDF native text + OCR fallback screenshot
- DOCX embedded image OCR screenshot
- SQLite cache warning screenshot
- Open WebUI tool configuration screenshot
- Open WebUI chat result screenshot

Do not include API keys in screenshots.

## Limitations

- OCR quality depends on image quality.
- CPU deployment can be slow for scanned PDFs and large images.
- OCR tables from images are returned as text, not as structured spreadsheets.
- SQLite cache is suitable for local and small deployments.
- Multi-instance production deployments may need shared cache storage or a managed database.
- The current `/ocr` endpoint processes requests synchronously.

## Files That Should Not Be Committed

```text
.env
data/
outputs/
.venv/
__pycache__/
```

## Important Repository Files

```text
README.md
.env.example
requirements.txt
requirements-paddle.txt
app/
scripts/create_sample_files.py
tests/
```

## Dependency and License Notes

This project uses PaddleOCR as the OCR backend.

Before production use, review the licenses and security status of:

- PaddleOCR
- PaddlePaddle
- FastAPI
- PyMuPDF
- python-docx
- Pillow
- other dependencies listed in the requirements files

# OpenWebUI PaddleOCR Backend

FastAPI OCR backend for Open WebUI using PaddleOCR.

This project provides a reusable OCR API that extracts text from images, PDF files, and DOCX documents. It is intended to be used together with an Open WebUI custom tool.

## Features

- FastAPI OCR backend
- Open WebUI custom tool integration
- API key authentication with `X-API-Key`
- PNG, JPG, JPEG, WEBP, BMP, TIFF/TIF image OCR
- PDF native text extraction
- PDF OCR fallback for scanned or image-based pages
- DOCX paragraph extraction
- DOCX table extraction
- OCR for images embedded inside DOCX files
- SQLite OCR result cache
- English and Latvian OCR test samples
- Structured JSON response with extracted text, pages, confidence and warnings
- Basic logging and error handling

## Supported File Types

| File type | Status | Processing |
|---|---:|---|
| PNG | Supported | Direct image OCR with PaddleOCR |
| JPG/JPEG | Supported | Direct image OCR with PaddleOCR |
| WEBP | Supported by tool/backend image pipeline | Direct image OCR if enabled in backend allowed extensions |
| BMP | Supported by tool/backend image pipeline | Direct image OCR if enabled in backend allowed extensions |
| TIFF/TIF | Supported by tool/backend image pipeline | Direct image OCR if enabled in backend allowed extensions |
| PDF | Supported | Native text extraction first, OCR fallback if needed |
| DOCX | Supported | Native text/tables + OCR for embedded images |

DOCX embedded images are extracted from the internal `word/media/` folder and OCR is applied to supported image formats.

## How Processing Works

### Images

Image files are validated first. If the file is valid, it is sent directly to PaddleOCR. The backend returns one page result with extracted text and OCR confidence.

### PDFs

PDF files are processed page by page.

1. The backend first tries to extract native/selectable PDF text.
2. If a page contains enough native text, OCR is skipped for that page.
3. If a page has little or no native text, the page is rendered as an image.
4. The rendered page image is processed with PaddleOCR.

This makes digital PDFs faster and scanned PDFs still usable.

### DOCX

DOCX files are processed in three parts:

1. Native paragraphs are extracted.
2. Native tables are extracted.
3. Embedded images are extracted from `word/media/` and processed with OCR.

This allows the backend to handle DOCX files that contain both editable text and image-based text.

### SQLite Cache

The backend stores successful OCR results in SQLite.

The cache key includes the file hash and OCR configuration. If the same file is uploaded again with the same OCR settings, the cached result is returned instead of processing the file again.

## Project Structure

```text
app/
  main.py                    FastAPI endpoints
  auth.py                    API key authentication
  cache.py                   SQLite OCR cache
  config.py                  environment settings
  schemas.py                 response models

  services/
    file_service.py          upload saving and file validation
    ocr_service.py           cache lookup, routing and response creation

  extractors/
    image_extractor.py       image validation and OCR
    pdf_extractor.py         PDF native extraction and OCR fallback
    docx_extractor.py        DOCX text, tables and embedded image OCR

  ocr/
    __init__.py              OCR engine loader
    paddle_engine.py         PaddleOCR integration
    mock_engine.py           mock OCR engine

tools/
  openwebui_ocr_tool.py      Open WebUI custom tool code

scripts/
  create_sample_files.py     generates test samples

tests/
  test_validation.py
```

## Local Setup

Clone the repository:

```bash
git clone https://github.com/ovaselis/openwebui-paddleocr-backend.git
cd openwebui-paddleocr-backend
```

Create and activate a virtual environment:

```bash
python3 -m venv ~/venvs/paddleocr-backend
source ~/venvs/paddleocr-backend/bin/activate
```

Install dependencies:

```bash
pip install -r requirements.txt
pip install -r requirements-paddle.txt
```

Create `.env`:

```bash
cp .env.example .env
nano .env
```

Example local configuration:

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

Start the backend:

```bash
python -m uvicorn app.main:app --host 0.0.0.0 --port 9713 --env-file .env
```

Health check:

```bash
curl http://127.0.0.1:9713/health
```

## API Usage

Set API key:

```bash
API_KEY=$(grep '^OCR_API_KEY=' .env | cut -d= -f2- | tr -d '\r')
```

Send a file:

```bash
curl --max-time 600 -X POST "http://127.0.0.1:9713/ocr" \
  -H "X-API-Key: $API_KEY" \
  -F "file=@samples/pdf/latvian_mixed_test.pdf"
```

Example response fields:

| Field | Description |
|---|---|
| `filename` | Original file name |
| `file_type` | `image`, `pdf`, or `docx` |
| `engine` | OCR engine |
| `language` | OCR language setting |
| `page_count` | Number of returned pages |
| `text` | Combined extracted text |
| `pages` | Page-level results |
| `confidence` | OCR confidence when available |
| `warnings` | Processing notes, fallback/cache messages |

## Open WebUI Tool

The Open WebUI custom tool code is stored in:

```text
tools/openwebui_ocr_tool.py
```

Local tool settings:

```text
OCR_API_URL=http://host.docker.internal:9713/ocr
OCR_API_KEY=<same value as backend OCR_API_KEY>
REQUEST_TIMEOUT_SECONDS=180
OPENWEBUI_UPLOADS_DIR=/app/backend/data/uploads
```

For Azure:

```text
OCR_API_URL=https://<your-azure-backend-domain>/ocr
OCR_API_KEY=<production-secret>
REQUEST_TIMEOUT_SECONDS=300
```

The tool should:

1. find the uploaded file in Open WebUI,
2. send it to the backend `/ocr` endpoint,
3. include `X-API-Key`,
4. read the JSON response,
5. return the extracted `text` field to the chat.

Do not commit real API keys in the tool code. Use placeholders or Open WebUI valves/settings.

## Azure Deployment

Recommended first Azure target: **Azure Container Apps**.

For an Azure Free Trial or CPU deployment, use conservative settings:

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

Digital PDFs and DOCX files should be reasonably fast because native extraction is used where possible. Scanned PDFs and image OCR are slower on CPU.

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

If PaddleOCR needs extra system libraries, add them to the image later.

### 2. Login to Azure

```bash
az login
az account set --subscription "<subscription-id>"
az extension add --name containerapp --upgrade
```

### 3. Create resource group

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

### 5. Configure environment variables

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

### 6. Test Azure backend

```bash
curl https://<your-container-app-url>/health
```

OCR test:

```bash
curl --max-time 600 -X POST "https://<your-container-app-url>/ocr" \
  -H "X-API-Key: <production-secret>" \
  -F "file=@samples/pdf/latvian_mixed_test.pdf"
```

### Azure Notes

For a first deployment, SQLite inside the container is acceptable for testing.

For production, consider:

- persistent storage for cache,
- Azure Files or Blob Storage,
- managed database if multiple replicas are used,
- stricter file size and page limits,
- GPU-capable infrastructure for large scanned-document OCR.

## Testing

Generate samples:

```bash
python scripts/create_sample_files.py
```

Generated samples:

```text
samples/images/
samples/pdf/
samples/docx/
```

Test commands:

```bash
curl --max-time 600 -X POST "http://127.0.0.1:9713/ocr" \
  -H "X-API-Key: $API_KEY" \
  -F "file=@samples/images/latvian_image_test.png"

curl --max-time 600 -X POST "http://127.0.0.1:9713/ocr" \
  -H "X-API-Key: $API_KEY" \
  -F "file=@samples/pdf/latvian_mixed_test.pdf"

curl --max-time 600 -X POST "http://127.0.0.1:9713/ocr" \
  -H "X-API-Key: $API_KEY" \
  -F "file=@samples/docx/latvian_docx_embedded_image_test.docx"
```

Tested coverage:

| Test | Status |
|---|---:|
| PNG/JPG OCR | Passed |
| English OCR | Passed |
| Latvian OCR | Passed |
| PDF native extraction | Passed |
| PDF OCR fallback | Passed |
| DOCX paragraphs | Passed |
| DOCX tables | Passed |
| DOCX embedded image OCR | Passed |
| SQLite cache | Passed |

## Functional Requirements Coverage

| Requirement | Status | Implementation |
|---|---:|---|
| FR-1 Open WebUI Integration | Done | Open WebUI custom tool calls FastAPI backend |
| FR-2 OCR Input Support | Done | Image OCR supported |
| FR-3 PDF Support | Done | Native extraction + OCR fallback |
| FR-4 OCR Backend Connection | Done | `/ocr` API endpoint |
| FR-5 Text Extraction Output | Done | Page-separated readable text |
| FR-6 Structured Output | Done | JSON with pages, confidence and warnings |
| FR-7 File Validation | Done | Extension and file validation |
| FR-8 Error Handling | Done | Clear HTTP errors and warnings |
| FR-9 Environment Configuration | Done | `.env` and `.env.example` |
| FR-10 Logging | Done | Startup, request, cache and error logs |

## Security Notes

- `/ocr` requires `X-API-Key`.
- `.env` is not committed.
- File size is limited.
- File types are validated.
- Temporary uploads are deleted.
- SQLite cache can contain extracted document text and should be protected.
- Production should use HTTPS.
- Do not expose the backend publicly without authentication.
- Do not commit real API keys.

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

## Limitations

- OCR quality depends on image quality.
- CPU deployment can be slow for scanned PDFs and large images.
- OCR tables from images are returned as text, not structured spreadsheets.
- SQLite cache is suitable for local and small deployments.
- Multi-instance production deployment needs shared cache storage or another database.
- The `/ocr` endpoint processes requests synchronously.

## Do Not Commit

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
tools/openwebui_ocr_tool.py
scripts/create_sample_files.py
tests/
```

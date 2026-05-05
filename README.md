# OpenWebUI PaddleOCR Backend

FastAPI OCR backend for Open WebUI using PaddleOCR.

This project is built for an Open WebUI custom OCR tool. The tool sends uploaded files to this backend, and the backend returns extracted text.

## Features

- Image OCR with PaddleOCR
- PDF native text extraction
- OCR fallback for scanned PDF pages
- DOCX paragraph and table extraction
- OCR for images embedded inside DOCX files
- SQLite cache to avoid re-processing the same file
- API key protection with `X-API-Key`
- Structured JSON output
- Basic logging and error handling
- Azure deployment plan

## Supported Files

Direct backend uploads:

| Type | Processing |
|---|---|
| PNG | PaddleOCR image OCR |
| JPG/JPEG | PaddleOCR image OCR |
| PDF | Native text first, OCR fallback if needed |
| DOCX | Native text/tables + embedded image OCR |

The Open WebUI tool also detects `WEBP`, `BMP`, `TIFF` and `TIF` images. To accept these as direct backend uploads, the same extensions must also be enabled in the backend configuration.
DOCX embedded images are extracted from `word/media/` and OCR is applied to supported image formats.

## How Processing Works

### Images

The backend validates the image and sends it directly to PaddleOCR.

### PDFs

Each PDF page is processed separately:

1. Try native/selectable PDF text extraction.
2. If native text is good enough, use it.
3. If native text is missing or too short, render the page as an image.
4. Run OCR on the rendered page.

This makes normal digital PDFs faster and scanned PDFs still usable.

### DOCX

DOCX processing extracts:

1. normal paragraphs,
2. native tables,
3. embedded images from `word/media/`, which are then OCR-processed.

### Cache

SQLite stores successful OCR results. If the same file is uploaded again with the same OCR settings, the cached result is returned.

## Project Structure

```text
app/
  main.py                    FastAPI endpoints
  auth.py                    API key check
  cache.py                   SQLite cache
  config.py                  environment settings
  schemas.py                 response models

  services/
    file_service.py          upload saving and extension validation
    ocr_service.py           cache lookup, routing, response building

  extractors/
    image_extractor.py       image OCR
    pdf_extractor.py         PDF native extraction + OCR fallback
    docx_extractor.py        DOCX text/tables/images

  ocr/
    paddle_engine.py         PaddleOCR integration
    mock_engine.py           mock engine for testing

tools/
  openwebui_ocr_tool.py      Open WebUI custom tool code

scripts/
  create_sample_files.py     creates test samples
```

## Environment Variables

Backend `.env` example:

```env
OCR_API_KEY=change-this-secret
OCR_ENGINE=paddleocr
OCR_LANG=lv
OCR_DEVICE=cpu

OCR_DETECTION_MODEL=PP-OCRv5_mobile_det
OCR_RECOGNITION_MODEL=latin_PP-OCRv5_mobile_rec

MAX_FILE_SIZE_MB=10
MAX_PDF_PAGES=10
PDF_DPI=150
PDF_NATIVE_TEXT_FIRST=true
PDF_NATIVE_MIN_CHARS=80

OCR_CACHE_ENABLED=true
OCR_CACHE_PATH=data/cache/ocr_cache.sqlite3

LOG_LEVEL=INFO
```

## Open WebUI Tool Setup

Tool file:

```text
tools/openwebui_ocr_tool.py
```

Recommended Azure tool valves:

```text
OCR_API_URL=https://<azure-container-app-url>/ocr
OCR_API_KEY=<production OCR_API_KEY>
REQUEST_TIMEOUT_SECONDS=300
OPENWEBUI_UPLOADS_DIR=/app/backend/data/uploads
DEBUG_MODE=false
```

The tool:

1. finds the uploaded file in Open WebUI,
2. sends it to the backend `/ocr` endpoint,
3. adds the `X-API-Key` header,
4. reads the backend JSON response,
5. returns the extracted `text` field to the chat.


## Azure Deployment

Recommended target: **Azure Container Apps**.

Azure Container Apps is suitable here because the backend is a containerized HTTP API. `az containerapp up` can build from source, push the image to a registry and deploy the app.

### 1. Add Dockerfile

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

If PaddleOCR needs extra Linux libraries in Azure, add them to this Dockerfile later.

### 2. Login and prepare Azure CLI

```bash
az login
az account set --subscription "<subscription-id>"
az extension add --name containerapp --upgrade
```

### 3. Deploy from repository source

From the repository root:

```bash
az containerapp up \
  --name openwebui-paddleocr-backend \
  --resource-group rg-openwebui-ocr \
  --location northeurope \
  --source . \
  --ingress external \
  --target-port 9713
```

The command outputs the Container App URL.

### 4. Configure backend environment variables

```bash
az containerapp update \
  --name openwebui-paddleocr-backend \
  --resource-group rg-openwebui-ocr \
  --set-env-vars \
    OCR_API_KEY="<production-secret>" \
    OCR_ENGINE="paddleocr" \
    OCR_LANG="lv" \
    OCR_DEVICE="cpu" \
    OCR_DETECTION_MODEL="PP-OCRv5_mobile_det" \
    OCR_RECOGNITION_MODEL="latin_PP-OCRv5_mobile_rec" \
    MAX_FILE_SIZE_MB="10" \
    MAX_PDF_PAGES="10" \
    PDF_DPI="150" \
    PDF_NATIVE_TEXT_FIRST="true" \
    PDF_NATIVE_MIN_CHARS="80" \
    OCR_CACHE_ENABLED="true" \
    OCR_CACHE_PATH="data/cache/ocr_cache.sqlite3" \
    LOG_LEVEL="INFO"
```

### 5. Test Azure backend

```bash
curl https://<azure-container-app-url>/health
```

OCR test:

```bash
curl --max-time 600 -X POST "https://<azure-container-app-url>/ocr" \
  -H "X-API-Key: <production-secret>" \
  -F "file=@samples/pdf/latvian_mixed_test.pdf"
```

### 6. Connect Open WebUI to Azure backend

In the Open WebUI tool valves:

```text
OCR_API_URL=https://<azure-container-app-url>/ocr
OCR_API_KEY=<same production secret>
REQUEST_TIMEOUT_SECONDS=300
```

Then upload a file in Open WebUI and call the OCR tool.

## Testing

Generate test samples:

```bash
python scripts/create_sample_files.py
```

Main tests:

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

Tested:

| Test | Status |
|---|---:|
| Image OCR | Passed |
| English OCR | Passed |
| Latvian OCR | Passed |
| PDF native extraction | Passed |
| PDF OCR fallback | Passed |
| DOCX paragraphs | Passed |
| DOCX tables | Passed |
| DOCX embedded image OCR | Passed |
| SQLite cache | Passed |

## Limitations

- OCR quality depends on source image quality.
- CPU deployment is slower for scanned PDFs and images.
- OCR tables from images are returned as text, not spreadsheets.
- SQLite cache is fine for local/small deployments, but production multi-replica deployment should use persistent/shared storage.
- Current `/ocr` processing is synchronous.

# Document OCR Backend MVP

Internal OCR backend for Open WebUI integration.

This is our own backend. It is not using Edgaras' Docker image. The project is only inspired by the same idea: upload a file to an API, process OCR, and return clean text.

## Current MVP features

- FastAPI backend
- `X-API-Key` authentication
- PNG/JPG/JPEG support
- scanned PDF support by rendering pages to images
- file type validation
- max file size limit
- max PDF page limit for laptop testing
- mock OCR engine for API testing
- optional PaddleOCR engine
- Markdown-style combined text output

## Why PaddleOCR?

PaddleOCR PP-OCRv5 supports multilingual OCR. Latvian is listed with language code `lv`, and the Latin recognition model includes Latvian among supported Latin-script languages.

For first testing, use `OCR_LANG=latin` because it covers Latvian + English style text better than a single-language setup.

## Local setup on Windows

Open PowerShell in this folder.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
copy .env.example .env
```

Edit `.env` and set your key:

```env
OCR_API_KEY=your-local-key
OCR_ENGINE=mock
OCR_LANG=latin
MAX_FILE_SIZE_MB=25
MAX_PDF_PAGES=3
PDF_DPI=200
```

Run:

```powershell
uvicorn app.main:app --reload --port 9713
```

Health check:

```powershell
curl http://127.0.0.1:9713/health
```

Test OCR with mock engine:

```powershell
curl.exe -X POST "http://127.0.0.1:9713/ocr" `
  -H "X-API-Key: your-local-key" `
  -F "file=@samples/test.jpg"
```

## Enable PaddleOCR

After the API works with `OCR_ENGINE=mock`, install PaddleOCR:

```powershell
pip install -r requirements-paddle.txt
```

Then change `.env`:

```env
OCR_ENGINE=paddleocr
OCR_LANG=latin
```

Restart uvicorn.

First PaddleOCR run may be slow because models are downloaded/loaded.

## Notes for laptop testing

Recommended first limits for an 8 GB VRAM laptop:

```env
MAX_PDF_PAGES=3
PDF_DPI=200
OCR_ENGINE=paddleocr
OCR_LANG=latin
```

Do not start with a 50-page scanned PDF. First test one clear JPG/PNG, then a 1-3 page PDF.

## Future phases

- add Open WebUI tool file
- add structured JSON/table output
- add DOCX/PPTX/XLSX parsing using Docling or Marker
- add PaddleOCR-VL / PP-StructureV3 for layout and tables
- add job queue for long documents
- add Docker deployment

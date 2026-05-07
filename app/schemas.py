from pydantic import BaseModel, Field

#defines JSON responses

class HealthResponse(BaseModel):
    status: str = "ok"
    engine: str
    language: str
    max_file_size_mb: int
    max_pdf_pages: int


class OCRPage(BaseModel):
    page: int
    text: str
    confidence: float | None = None


class OCRResponse(BaseModel):
    filename: str
    file_type: str
    engine: str
    language: str
    page_count: int
    text: str
    pages: list[OCRPage]
    warnings: list[str] = Field(default_factory=list) #every response creates a new list

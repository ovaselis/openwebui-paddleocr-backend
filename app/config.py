from pathlib import Path
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    api_key: str = Field(default="local-test-key-123", alias="OCR_API_KEY")
    ocr_engine: str = Field(default="mock", alias="OCR_ENGINE")
    ocr_lang: str = Field(default="latin", alias="OCR_LANG")
    max_file_size_mb: int = Field(default=25, alias="MAX_FILE_SIZE_MB")
    max_pdf_pages: int = Field(default=3, alias="MAX_PDF_PAGES")
    pdf_dpi: int = Field(default=200, alias="PDF_DPI")
    pdf_native_text_first: bool = Field(default=True, alias="PDF_NATIVE_TEXT_FIRST")
    pdf_native_min_chars: int = Field(default=80, alias="PDF_NATIVE_MIN_CHARS")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    data_dir: Path = Path("data")
    upload_dir: Path = Path("data/uploads")
    allowed_extensions: set[str] = {".png", ".jpg", ".jpeg", ".pdf", ".docx"}

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()

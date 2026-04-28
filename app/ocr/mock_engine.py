from pathlib import Path


class MockOCREngine:
    name = "mock"

    async def extract_text(self, image_path: Path) -> tuple[str, float | None]:
        return (
            f"[MOCK OCR RESULT]\nFile: {image_path.name}\n"
            "This proves that upload, validation, API authentication, and response formatting work.",
            1.0,
        )

from typing import Annotated

from fastapi import Header, HTTPException, status

from app.config import settings


async def require_api_key(x_api_key: Annotated[str | None, Header()] = None) -> None:
    # Require X-API-Key unless OCR_API_KEY is empty.
    if settings.api_key and x_api_key != settings.api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing X-API-Key header.",
        )

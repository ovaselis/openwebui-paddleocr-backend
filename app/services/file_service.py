import uuid
from pathlib import Path

from fastapi import HTTPException, UploadFile, status

from app.config import settings


def get_file_suffix(filename: str) -> str:
    # gets the extension, for example ".pdf", ".png", ".docx"
    return Path(filename).suffix.lower()


def validate_file_extension(suffix: str) -> None:
    # checks if file type is allowed
    if suffix not in settings.allowed_extensions:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=(
                f"Unsupported file type '{suffix}'. "
                f"Supported: {sorted(settings.allowed_extensions)}"
            ),
        )


async def save_upload(file: UploadFile, suffix: str) -> Path:
    # creates upload directory if it does not exist
    settings.upload_dir.mkdir(parents=True, exist_ok=True)

    # saves uploaded file in temporary dir with a unique random name
    saved_path = settings.upload_dir / f"{uuid.uuid4().hex}{suffix}"

    # converts max file size from MB to bytes
    max_size_bytes = settings.max_file_size_mb * 1024 * 1024
    total_size = 0

    with saved_path.open("wb") as output:
        while True:
            # reads uploaded file in 1 MB chunks
            chunk = await file.read(1024 * 1024)

            if not chunk:
                break

            total_size += len(chunk)

            # stops upload if file is larger than allowed
            if total_size > max_size_bytes:
                output.close()
                saved_path.unlink(missing_ok=True)
                raise HTTPException(
                    status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    detail=(
                        f"File is too large. Maximum allowed size is "
                        f"{settings.max_file_size_mb} MB."
                    ),
                )

            output.write(chunk)

    return saved_path

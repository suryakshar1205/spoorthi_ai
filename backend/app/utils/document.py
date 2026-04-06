from __future__ import annotations

from io import BytesIO
from pathlib import Path

from fastapi import HTTPException, UploadFile, status
from pypdf import PdfReader

from app.utils.text import structured_text


SUPPORTED_EXTENSIONS = {".pdf", ".txt", ".md"}


def validate_upload(filename: str) -> str:
    extension = Path(filename).suffix.lower()
    if extension not in SUPPORTED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only PDF, TXT, and MD files are supported.",
        )
    return extension


async def extract_text_from_upload(upload: UploadFile) -> str:
    extension = validate_upload(upload.filename or "")
    content = await upload.read()
    return _extract_text_from_content(content, extension)


def extract_text_from_path(path: Path) -> str:
    extension = validate_upload(path.name)
    content = path.read_bytes()
    return _extract_text_from_content(content, extension)


def _extract_text_from_content(content: bytes, extension: str) -> str:

    if not content:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file is empty.",
        )

    if extension in {".txt", ".md"}:
        return structured_text(_decode_text(content))

    reader = PdfReader(BytesIO(content))
    extracted = "\n\n".join(page.extract_text() or "" for page in reader.pages)
    return structured_text(extracted)


def _decode_text(content: bytes) -> str:
    for encoding in ("utf-8", "utf-16", "latin-1"):
        try:
            return content.decode(encoding).strip()
        except UnicodeDecodeError:
            continue
    return content.decode("utf-8", errors="ignore").strip()

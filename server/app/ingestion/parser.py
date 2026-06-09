import asyncio
from pathlib import Path
from typing import Optional

from ..api.errors import UnsupportedFileTypeError
from ..schemas.discovery import ParsedDocument
from .extractors.docx import extract_docx
from .extractors.pdf import extract_pdf
from .extractors.xlsx_csv import extract_csv, extract_xlsx

# Extension takes priority over Content-Type header (browsers can be wrong)
_EXT_TO_FORMAT: dict[str, str] = {
    ".pdf": "pdf",
    ".docx": "docx",
    ".doc": "docx",
    ".xlsx": "xlsx",
    ".xls": "xlsx",
    ".csv": "csv",
}

_MIME_TO_FORMAT: dict[str, str] = {
    "application/pdf": "pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "docx",
    "application/msword": "docx",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": "xlsx",
    "application/vnd.ms-excel": "xlsx",
    "text/csv": "csv",
    "application/csv": "csv",
    "text/plain": "csv",  # allow .txt uploads treated as CSV
}


def _detect_format(filename: str, content_type: str) -> str:
    ext = Path(filename).suffix.lower()
    fmt = _EXT_TO_FORMAT.get(ext) or _MIME_TO_FORMAT.get(
        content_type.split(";")[0].strip().lower()
    )
    if not fmt:
        raise UnsupportedFileTypeError(
            f"Unsupported file type '{ext or content_type}'. "
            "Accepted: .pdf, .docx, .xlsx, .csv"
        )
    return fmt


async def parse(
    content: bytes,
    filename: str,
    content_type: str,
    max_rows: Optional[int] = None,
) -> ParsedDocument:
    """
    Dispatch to the right extractor based on filename extension (with MIME fallback).
    All extractors are sync and run in a thread pool to avoid blocking the event loop.
    """
    fmt = _detect_format(filename, content_type)

    if fmt == "pdf":
        return await asyncio.to_thread(extract_pdf, content, filename, max_rows)
    if fmt == "docx":
        return await asyncio.to_thread(extract_docx, content, filename, max_rows)
    if fmt == "xlsx":
        return await asyncio.to_thread(extract_xlsx, content, filename, max_rows)
    if fmt == "csv":
        return await asyncio.to_thread(extract_csv, content, filename, max_rows)

    # unreachable — _detect_format always raises or returns a known fmt
    raise UnsupportedFileTypeError(f"Unhandled format '{fmt}'")

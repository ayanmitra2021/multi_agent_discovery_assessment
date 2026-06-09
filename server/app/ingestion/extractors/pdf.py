import io
from typing import Optional

import pdfplumber

from ...api.errors import DocumentParseError
from ...schemas.discovery import ParsedDocument, TableBlock


def extract_pdf(
    content: bytes,
    filename: str,
    max_rows: Optional[int] = None,
) -> ParsedDocument:
    text_blocks: list[str] = []
    table_blocks: list[TableBlock] = []
    warnings: list[str] = []
    page_count = 0

    try:
        with pdfplumber.open(io.BytesIO(content)) as pdf:
            page_count = len(pdf.pages)
            for page in pdf.pages:
                text = page.extract_text()
                if text and text.strip():
                    text_blocks.append(text.strip())

                for table in page.extract_tables() or []:
                    if not table:
                        continue
                    headers = [str(cell or "").strip() for cell in table[0]]
                    rows = [
                        [str(cell or "").strip() for cell in row]
                        for row in table[1:]
                    ]
                    if max_rows and len(rows) > max_rows:
                        rows = rows[:max_rows]
                        warnings.append(
                            f"Table truncated to {max_rows} rows (MAX_APPS_PER_RUN limit)"
                        )
                    table_blocks.append(TableBlock(headers=headers, rows=rows))

    except Exception as exc:
        raise DocumentParseError(f"Failed to parse PDF '{filename}': {exc}") from exc

    if not text_blocks and not table_blocks:
        warnings.append(
            "No extractable text found — document may be image-based or scanned"
        )

    return ParsedDocument(
        filename=filename,
        content_type="application/pdf",
        text_blocks=text_blocks,
        table_blocks=table_blocks,
        metadata={"page_count": page_count},
        warnings=warnings,
    )

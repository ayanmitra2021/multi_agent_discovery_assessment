from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile

from ..api.errors import FileTooLargeError
from ..ingestion.parser import parse
from ..schemas.api import AssessResponse
from ..schemas.enums import CSP

router = APIRouter(tags=["assessment"])


@router.post("/assess", response_model=AssessResponse)
async def create_assessment(
    request: Request,
    file: UploadFile = File(...),
    csp: CSP = Form(...),
) -> AssessResponse:
    settings = request.app.state.settings

    content = await file.read()
    max_bytes = settings.max_upload_size_mb * 1024 * 1024
    if len(content) > max_bytes:
        raise FileTooLargeError(settings.max_upload_size_mb)

    # Parse and validate — raises UnsupportedFileTypeError (422) or
    # DocumentParseError (422) on bad input before touching the LLM pipeline.
    await parse(
        content=content,
        filename=file.filename or "upload",
        content_type=file.content_type or "",
        max_rows=settings.max_apps_per_run,
    )

    # Orchestrator wired in Phase 5.
    raise HTTPException(status_code=501, detail="Assessment pipeline not yet implemented")

from typing import Optional
from pydantic import BaseModel
from .enums import AssessmentStatus
from .report import AssessmentReport


class AssessResponse(BaseModel):
    assessment_id: str
    status: AssessmentStatus
    report: Optional[AssessmentReport] = None
    errors: list[str] = []


class HealthResponse(BaseModel):
    status: str = "ok"
    version: str
    llm_provider: str

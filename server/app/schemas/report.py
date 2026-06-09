from datetime import datetime, timezone
from typing import Optional
from pydantic import BaseModel, Field
from .enums import CSP, AssessmentStatus
from .discovery import AppProfile
from .policies import PolicyContext
from .architecture import ArchitecturePlan
from .estimation import EstimationReport


class AssessmentReport(BaseModel):
    assessment_id: str
    target_csp: CSP
    status: AssessmentStatus
    app_profile: Optional[AppProfile] = None
    policy_context: Optional[PolicyContext] = None
    architecture_plan: Optional[ArchitecturePlan] = None
    estimation_report: Optional[EstimationReport] = None
    executive_summary: str = ""
    errors: list[str] = []
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

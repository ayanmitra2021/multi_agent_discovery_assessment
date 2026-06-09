from pydantic import BaseModel, Field
from .enums import Workstream


class WorkstreamEstimate(BaseModel):
    workstream: Workstream
    effort_days_min: int
    effort_days_max: int
    description: str = ""


class Wave(BaseModel):
    wave_number: int
    apps: list[str]
    rationale: str = ""
    estimated_weeks: int = 0


class EstimationReport(BaseModel):
    workstream_estimates: list[WorkstreamEstimate] = []
    total_weeks_min: int = 0
    total_weeks_max: int = 0
    team_size_fte: int = 0
    waves: list[Wave] = []
    assumptions: list[str] = []
    risks: list[str] = []
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)

from typing import Optional
from pydantic import BaseModel, Field
from .enums import MigrationStrategy


class ServiceMapping(BaseModel):
    source_component: str
    target_service: str
    rationale: Optional[str] = None


class ArchitecturePlan(BaseModel):
    migration_strategy: MigrationStrategy
    target_services: list[ServiceMapping] = []
    landing_zone_pattern: str = ""
    security_controls: list[str] = []
    rationale: str = ""
    policy_compliance_notes: list[str] = []
    risks: list[str] = []
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)

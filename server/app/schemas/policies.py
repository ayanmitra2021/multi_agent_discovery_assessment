from typing import Optional
from pydantic import BaseModel
from .enums import CSP


class Control(BaseModel):
    code: str
    title: str
    category: str
    severity: str  # critical | high | medium | low
    is_mandatory: bool
    description: str
    source_ref: Optional[str] = None


class ApprovedService(BaseModel):
    service_name: str
    service_category: str
    capability_tags: list[str] = []
    constraints_note: Optional[str] = None


class ComplianceFramework(BaseModel):
    framework_code: str
    framework_name: str
    jurisdiction: Optional[str] = None
    version: Optional[str] = None


class PolicyContext(BaseModel):
    csp: CSP
    controls: list[Control] = []
    approved_services: list[ApprovedService] = []
    compliance_frameworks: list[ComplianceFramework] = []
    landing_zone_standards: list[str] = []
    escalation_flags: list[str] = []

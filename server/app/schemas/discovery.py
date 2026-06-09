from typing import Optional
from pydantic import BaseModel, Field
from .enums import ComplexityTier


class TableBlock(BaseModel):
    sheet_name: Optional[str] = None
    headers: list[str] = []
    rows: list[list[str]] = []


class ParsedDocument(BaseModel):
    filename: str
    content_type: str
    text_blocks: list[str] = []
    table_blocks: list[TableBlock] = []
    metadata: dict = {}
    warnings: list[str] = []


class TechStack(BaseModel):
    languages: list[str] = []
    frameworks: list[str] = []
    databases: list[str] = []
    os_platform: Optional[str] = None
    runtime_versions: dict[str, str] = {}
    containerized: bool = False


class Dependency(BaseModel):
    name: str
    dep_type: str = "external"  # internal | external | third-party
    protocol: Optional[str] = None
    notes: Optional[str] = None


class AppProfile(BaseModel):
    app_name: str
    owner: Optional[str] = None
    business_criticality: Optional[str] = None
    tech_stack: TechStack = Field(default_factory=TechStack)
    dependencies: list[Dependency] = []
    tech_debt_indicators: list[str] = []
    cloud_readiness_signals: list[str] = []
    complexity_tier: ComplexityTier = ComplexityTier.medium
    data_residency_constraints: list[str] = []
    notes: list[str] = []
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)

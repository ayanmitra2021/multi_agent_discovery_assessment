from enum import StrEnum


class CSP(StrEnum):
    aws = "aws"
    azure = "azure"
    gcp = "gcp"


class MigrationStrategy(StrEnum):
    rehost = "rehost"
    replatform = "replatform"
    refactor = "refactor"
    replace = "replace"
    retire = "retire"


class ComplexityTier(StrEnum):
    low = "low"
    medium = "medium"
    high = "high"
    critical = "critical"


class AssessmentStatus(StrEnum):
    running = "running"
    completed = "completed"
    partial = "partial"
    failed = "failed"


class Workstream(StrEnum):
    infrastructure = "infrastructure"
    application = "application"
    data = "data"
    testing = "testing"


class LLMProvider(StrEnum):
    claude = "claude"
    openai = "openai"
    gemini = "gemini"


class EstimationModel(StrEnum):
    parametric = "parametric"
    analogous = "analogous"


class ReportFormat(StrEnum):
    docx = "docx"
    pdf = "pdf"
    json = "json"
    markdown = "markdown"

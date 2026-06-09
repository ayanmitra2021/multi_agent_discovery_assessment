from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from .schemas.enums import LLMProvider, CSP, EstimationModel, ReportFormat


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # LLM
    llm_provider: LLMProvider = LLMProvider.claude
    anthropic_api_key: str = ""
    openai_api_key: str = ""

    # Migration defaults
    default_target_cloud: CSP = CSP.aws
    enable_multi_agent: bool = True
    estimation_model: EstimationModel = EstimationModel.parametric
    max_apps_per_run: int = Field(default=50, ge=1, le=200)

    # Report
    report_format: ReportFormat = ReportFormat.json
    report_output_dir: str = "./outputs"

    # Upload
    max_upload_size_mb: int = Field(default=25, ge=1, le=100)

    # Databases
    policies_db_url: str = "sqlite+aiosqlite:///./data/policies.sqlite"
    audit_db_url: str = "sqlite+aiosqlite:///./data/audit.sqlite"

"""
DiscoveryAgent — extracts a structured AppProfile from an uploaded document.

Uses generate_structured() so the LLM returns JSON validated directly against
the AppProfile Pydantic model.  No tool loop is needed here; the document
content is provided in full as the user message.
"""
from ..llm.base import LLMClient
from ..schemas.discovery import AppProfile, ParsedDocument
from .base import AssessmentContext, BaseAgent

_SYSTEM_PROMPT = """\
You are a cloud migration discovery specialist. Analyse the provided application
portfolio document and extract a structured profile of the application.

## Fields to extract

app_name        — canonical application name; infer from doc title or first heading
owner           — team or person responsible; null if not mentioned
business_criticality — one of: mission-critical | business-important | standard | low-value
                  Infer from language like "core banking", "revenue-generating", "internal tool"
tech_stack:
  languages       — programming languages (e.g. Java, Python, C#)
  frameworks      — web/app frameworks (e.g. Spring Boot, Django, .NET MVC)
  databases       — database products (e.g. Oracle 12c, SQL Server, MongoDB)
  os_platform     — OS and version if mentioned (e.g. Windows Server 2016, RHEL 8)
  runtime_versions — dict of runtime → version (e.g. {"java": "8", "node": "16"})
  containerized   — true if Docker/Kubernetes/containers are mentioned
dependencies    — list of integrations; for each give:
  name            — system or service name
  dep_type        — internal | external | third-party
  protocol        — REST | SOAP | MQ | JDBC | SFTP | etc. (null if unknown)
  notes           — any relevant note
tech_debt_indicators — list of strings describing debt signals, e.g.:
  "End-of-life runtime (Java 8)", "No CI/CD pipeline", "Monolithic architecture",
  "Manual deployments", "Hardcoded configuration", "No automated tests"
cloud_readiness_signals — list of strings describing positive signals, e.g.:
  "Stateless services", "REST API", "Existing Docker containers",
  "12-factor compliance", "Automated build pipeline"
complexity_tier — low | medium | high | critical
  low      = simple, stateless, modern stack, few dependencies
  medium   = moderate complexity, some integrations, standard tech
  high     = legacy runtime, many integrations, significant tech debt
  critical = mainframe, proprietary middleware, mission-critical with 10+ dependencies
data_residency_constraints — list any GDPR, data sovereignty, or geographic
  restrictions explicitly mentioned
notes           — anything else relevant to migration planning
confidence      — float 0.0–1.0; lower when the document is sparse or ambiguous

## Rules
- Extract ONLY what is explicitly stated or strongly implied.
- Do NOT invent information not present in the document.
- For missing fields use null / empty list as appropriate.
- Set confidence < 0.6 when key sections are absent.
"""


def _format_document(doc: ParsedDocument) -> str:
    """Flatten all text and table blocks from a ParsedDocument into a single string."""
    parts: list[str] = [f"# Document: {doc.filename}\n"]

    for block in doc.text_blocks:
        if block.strip():
            parts.append(block)

    for table in doc.table_blocks:
        header = f"\n## Table: {table.sheet_name or 'unnamed'}"
        parts.append(header)
        if table.headers:
            parts.append(" | ".join(table.headers))
            parts.append(" | ".join(["---"] * len(table.headers)))
        for row in table.rows:
            parts.append(" | ".join(str(c) for c in row))

    if doc.warnings:
        parts.append("\n## Parser warnings\n" + "\n".join(f"- {w}" for w in doc.warnings))

    return "\n\n".join(parts)


class DiscoveryAgent(BaseAgent):
    """Extracts a structured AppProfile from a parsed document."""

    def __init__(self, llm: LLMClient) -> None:
        self._llm = llm

    async def run(self, ctx: AssessmentContext) -> AppProfile:
        self._log(ctx, "started", document=ctx.document.filename)

        document_text = _format_document(ctx.document)
        messages = [{"role": "user", "content": document_text}]

        profile = await self._llm.generate_structured(
            messages=messages,
            output_type=AppProfile,
            system=_SYSTEM_PROMPT,
        )

        self._log(
            ctx,
            "completed",
            app_name=profile.app_name,
            complexity_tier=str(profile.complexity_tier),
            tech_debt_count=len(profile.tech_debt_indicators),
            confidence=profile.confidence,
        )
        return profile

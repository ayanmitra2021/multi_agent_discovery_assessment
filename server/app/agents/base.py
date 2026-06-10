"""
Base types shared by all agents.

AssessmentContext is threaded through every agent so audit events and
shared state are centralised in a single mutable object per request.
"""
import uuid
from abc import ABC
from dataclasses import dataclass, field
from datetime import datetime, timezone

from ..schemas.discovery import ParsedDocument
from ..schemas.enums import CSP


@dataclass
class AssessmentContext:
    """Carries per-request state and the audit trail across all agents."""

    session_id: str
    document: ParsedDocument
    target_csp: CSP
    enable_multi_agent: bool
    audit_log: list[dict] = field(default_factory=list)

    @classmethod
    def create(
        cls,
        document: ParsedDocument,
        target_csp: CSP,
        enable_multi_agent: bool = True,
    ) -> "AssessmentContext":
        return cls(
            session_id=str(uuid.uuid4()),
            document=document,
            target_csp=target_csp,
            enable_multi_agent=enable_multi_agent,
        )


class BaseAgent(ABC):
    """Minimal contract for all pipeline agents."""

    def _log(self, ctx: AssessmentContext, event: str, **kwargs) -> None:
        ctx.audit_log.append(
            {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "agent": self.__class__.__name__,
                "event": event,
                **kwargs,
            }
        )

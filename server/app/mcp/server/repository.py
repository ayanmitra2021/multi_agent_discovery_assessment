"""
SQLAlchemy query functions for all four MCP tool handlers.
Each function takes a Session and returns plain dicts (JSON-serialisable).
"""
from typing import Optional

from sqlalchemy import or_
from sqlalchemy.orm import Session

from ...persistence.policies_db import (
    ApprovedService,
    ComplianceFramework,
    PastMigration,
    Policy,
)


def get_policies(
    session: Session,
    csp: str,
    categories: Optional[list[str]] = None,
    mandatory_only: bool = False,
) -> list[dict]:
    q = session.query(Policy).filter(Policy.csp == csp.lower())
    if categories:
        q = q.filter(Policy.category.in_([c.lower() for c in categories]))
    if mandatory_only:
        q = q.filter(Policy.is_mandatory.is_(True))
    return [
        {
            "control_code": p.control_code,
            "csp": p.csp,
            "title": p.title,
            "category": p.category,
            "severity": p.severity,
            "is_mandatory": p.is_mandatory,
            "description": p.description,
            "source_ref": p.source_ref,
        }
        for p in q.order_by(Policy.severity, Policy.control_code).all()
    ]


def get_approved_services(
    session: Session,
    csp: str,
    capability_tags: Optional[list[str]] = None,
    status: str = "approved",
) -> list[dict]:
    q = (
        session.query(ApprovedService)
        .filter(
            ApprovedService.csp == csp.lower(),
            ApprovedService.status == status,
        )
    )
    services = q.order_by(ApprovedService.service_category, ApprovedService.service_name).all()

    # SQLite JSON arrays: filter in Python (data set is small enough)
    if capability_tags:
        tags_lower = [t.lower() for t in capability_tags]
        services = [
            s for s in services
            if any(tag in [ct.lower() for ct in (s.capability_tags or [])]
                   for tag in tags_lower)
        ]

    return [
        {
            "service_name": s.service_name,
            "csp": s.csp,
            "service_category": s.service_category,
            "capability_tags": s.capability_tags or [],
            "status": s.status,
            "constraints_note": s.constraints_note,
        }
        for s in services
    ]


def get_compliance_frameworks(
    session: Session,
    csp: Optional[str] = None,        # reserved for future CSP-specific filtering
    jurisdiction: Optional[str] = None,
    framework_codes: Optional[list[str]] = None,
) -> list[dict]:
    q = session.query(ComplianceFramework)
    if jurisdiction:
        q = q.filter(ComplianceFramework.jurisdiction == jurisdiction)
    if framework_codes:
        q = q.filter(
            ComplianceFramework.framework_code.in_([c.upper() for c in framework_codes])
        )
    return [
        {
            "framework_code": f.framework_code,
            "framework_name": f.framework_name,
            "jurisdiction": f.jurisdiction,
            "version": f.version,
        }
        for f in q.order_by(ComplianceFramework.framework_code).all()
    ]


def search_past_migrations(
    session: Session,
    csp: str,
    app_archetype: Optional[str] = None,
    complexity_tier: Optional[str] = None,
    keywords: Optional[str] = None,
    limit: int = 5,
) -> list[dict]:
    q = session.query(PastMigration).filter(PastMigration.csp == csp.lower())
    if app_archetype:
        q = q.filter(PastMigration.app_archetype == app_archetype.lower())
    if complexity_tier:
        q = q.filter(PastMigration.complexity_tier == complexity_tier.lower())
    if keywords:
        pattern = f"%{keywords}%"
        q = q.filter(
            or_(
                PastMigration.source_pattern.ilike(pattern),
                PastMigration.target_pattern.ilike(pattern),
                PastMigration.lessons_learned.ilike(pattern),
            )
        )
    results = q.limit(limit).all()
    return [
        {
            "csp": m.csp,
            "source_pattern": m.source_pattern,
            "target_pattern": m.target_pattern,
            "app_archetype": m.app_archetype,
            "complexity_tier": m.complexity_tier,
            "outcome": m.outcome,
            "duration_weeks": m.duration_weeks,
            "lessons_learned": m.lessons_learned,
        }
        for m in results
    ]

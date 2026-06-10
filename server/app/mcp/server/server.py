"""
FastMCP server for cloud migration policies.

Run as:   py -m app.mcp.server.server
Env var:  POLICIES_DB_URL  (defaults to sqlite:///./data/policies.sqlite)

The server exposes four read-only tools backed by a SQLite policies database.
"""
import json
import os
import sys
from pathlib import Path
from typing import Annotated, Optional

from mcp.server.fastmcp import FastMCP
from pydantic import Field
from sqlalchemy.orm import Session

# Ensure 'server/' is on sys.path when launched as a subprocess
_server_root = str(Path(__file__).resolve().parents[3])
if _server_root not in sys.path:
    sys.path.insert(0, _server_root)

from app.persistence.policies_db import create_db_engine, init_db
from app.persistence.seed.policies_seed import seed_database
from app.mcp.server import repository

_DB_URL = os.environ.get("POLICIES_DB_URL", "sqlite:///./data/policies.sqlite")
_engine = create_db_engine(_DB_URL)
init_db(_engine)
seed_database(_engine)

mcp = FastMCP("cloud-policies-server")


@mcp.tool(
    name="get_policies",
    description="Get the list of policies and best practices advised by your organisation",
)
def get_policies(
    csp: Annotated[
        str,
        Field(description="Target cloud provider. One of: aws | azure | gcp"),
    ],
    categories: Annotated[
        Optional[list[str]],
        Field(
            description=(
                "Optional list of policy categories to filter by. "
                "Valid values: security | networking | operations | architecture | cost. "
                "Omit to return all categories."
            )
        ),
    ] = None,
    mandatory_only: Annotated[
        bool,
        Field(
            description=(
                "When True, return only mandatory controls that must be satisfied "
                "for every migration. When False (default), return all policies "
                "including recommended ones."
            )
        ),
    ] = False,
) -> str:
    """Return migration policies and controls for the target cloud provider."""
    with Session(_engine) as session:
        results = repository.get_policies(session, csp, categories, mandatory_only)
    return json.dumps(results)


@mcp.tool(
    name="get_approved_services",
    description=(
        "Get the list of cloud services approved by the organisation for use "
        "in migration target architectures"
    ),
)
def get_approved_services(
    csp: Annotated[
        str,
        Field(description="Target cloud provider. One of: aws | azure | gcp"),
    ],
    capability_tags: Annotated[
        Optional[list[str]],
        Field(
            description=(
                "Optional list of capability tags to narrow results to services "
                "that match the workload's requirements. "
                "Examples: containers | serverless | relational | nosql | "
                "object-storage | messaging | analytics | kubernetes | event-driven. "
                "Omit to return all approved services for the CSP."
            )
        ),
    ] = None,
    status: Annotated[
        str,
        Field(
            description=(
                "Filter by service approval status. "
                "approved — fully approved for production use (default). "
                "conditional — approved with constraints; check constraints_note before recommending. "
                "deprecated — no longer recommended; avoid for new migrations."
            )
        ),
    ] = "approved",
) -> str:
    """Return approved cloud services for the target cloud provider."""
    with Session(_engine) as session:
        results = repository.get_approved_services(session, csp, capability_tags, status)
    return json.dumps(results)


@mcp.tool(
    name="get_compliance_frameworks",
    description=(
        "Get applicable compliance frameworks and regulatory requirements "
        "relevant to the migration workload"
    ),
)
def get_compliance_frameworks(
    csp: Annotated[
        Optional[str],
        Field(
            description=(
                "Optional cloud provider for context (aws | azure | gcp). "
                "Frameworks are CSP-agnostic; this parameter is accepted for "
                "future CSP-specific filtering."
            )
        ),
    ] = None,
    jurisdiction: Annotated[
        Optional[str],
        Field(
            description=(
                "Optional jurisdiction to filter frameworks by geography. "
                "One of: US | EU | International | UK | APAC. "
                "For example, pass 'EU' to retrieve GDPR-related frameworks."
            )
        ),
    ] = None,
    framework_codes: Annotated[
        Optional[list[str]],
        Field(
            description=(
                "Optional list of specific framework codes to retrieve. "
                "Known codes: SOC2 | ISO27001 | GDPR | PCIDSS | HIPAA. "
                "Matching is case-insensitive. Omit to return all frameworks."
            )
        ),
    ] = None,
) -> str:
    """Return applicable compliance frameworks."""
    with Session(_engine) as session:
        results = repository.get_compliance_frameworks(session, csp, jurisdiction, framework_codes)
    return json.dumps(results)


@mcp.tool(
    name="search_past_migrations",
    description=(
        "Search historical migration patterns and lessons learned from past cloud "
        "migrations to inform effort estimates and architecture decisions"
    ),
)
def search_past_migrations(
    csp: Annotated[
        str,
        Field(description="Target cloud provider. One of: aws | azure | gcp"),
    ],
    app_archetype: Annotated[
        Optional[str],
        Field(
            description=(
                "Optional application archetype to narrow results to similar workloads. "
                "One of: web | api | batch | legacy-desktop | analytics | database | mobile. "
                "For example, use 'legacy-desktop' for VB6 or WinForms migrations."
            )
        ),
    ] = None,
    complexity_tier: Annotated[
        Optional[str],
        Field(
            description=(
                "Optional complexity tier to filter by migration difficulty. "
                "One of: low | medium | high | critical. "
                "Match to the Discovery Agent's assessed complexity_tier for the best analogy."
            )
        ),
    ] = None,
    keywords: Annotated[
        Optional[str],
        Field(
            description=(
                "Optional free-text keyword to search across source pattern, target pattern, "
                "and lessons learned. Useful for finding migrations involving a specific "
                "technology, e.g. 'Oracle', 'VB6', 'SAP', 'Kubernetes', 'Hadoop'."
            )
        ),
    ] = None,
    limit: Annotated[
        int,
        Field(
            description=(
                "Maximum number of migration records to return. Default is 5. "
                "Increase to 10 when building effort estimates to get a wider analogy base."
            )
        ),
    ] = 5,
) -> str:
    """Search historical migration patterns for effort and lessons-learned data."""
    with Session(_engine) as session:
        results = repository.search_past_migrations(
            session, csp, app_archetype, complexity_tier, keywords, limit
        )
    return json.dumps(results)


if __name__ == "__main__":
    mcp.run()

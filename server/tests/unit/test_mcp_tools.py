"""
Unit tests for the MCP tool repository functions.
Uses in-memory SQLite seeded with real data — no subprocess or MCP protocol involved.
"""
import pytest
from sqlalchemy.orm import Session

from app.mcp.server.repository import (
    get_approved_services,
    get_compliance_frameworks,
    get_policies,
    search_past_migrations,
)
from app.persistence.policies_db import Base, create_db_engine, init_db
from app.persistence.seed.policies_seed import seed_database


@pytest.fixture(scope="module")
def db_session():
    """In-memory DB seeded once for the whole module."""
    engine = create_db_engine("sqlite:///:memory:")
    init_db(engine)
    seed_database(engine)
    with Session(engine) as session:
        yield session


# ---------------------------------------------------------------------------
# get_policies
# ---------------------------------------------------------------------------

class TestGetPolicies:
    def test_returns_policies_for_aws(self, db_session):
        results = get_policies(db_session, "aws")
        assert len(results) > 0
        assert all(p["csp"] == "aws" for p in results)

    def test_returns_policies_for_azure(self, db_session):
        results = get_policies(db_session, "azure")
        assert len(results) > 0
        assert all(p["csp"] == "azure" for p in results)

    def test_returns_policies_for_gcp(self, db_session):
        results = get_policies(db_session, "gcp")
        assert len(results) > 0
        assert all(p["csp"] == "gcp" for p in results)

    def test_csp_case_insensitive(self, db_session):
        upper = get_policies(db_session, "AWS")
        lower = get_policies(db_session, "aws")
        assert len(upper) == len(lower)

    def test_mandatory_only_filter(self, db_session):
        results = get_policies(db_session, "aws", mandatory_only=True)
        assert len(results) > 0
        assert all(p["is_mandatory"] for p in results)

    def test_category_filter(self, db_session):
        results = get_policies(db_session, "aws", categories=["security"])
        assert len(results) > 0
        assert all(p["category"] == "security" for p in results)

    def test_multiple_categories(self, db_session):
        results = get_policies(db_session, "aws", categories=["security", "networking"])
        categories = {p["category"] for p in results}
        assert "security" in categories
        assert "networking" in categories

    def test_unknown_csp_returns_empty(self, db_session):
        results = get_policies(db_session, "alibaba")
        assert results == []

    def test_result_has_required_fields(self, db_session):
        results = get_policies(db_session, "aws")
        required = {"control_code", "title", "severity", "is_mandatory", "description"}
        assert required.issubset(results[0].keys())

    def test_mandatory_and_category_combined(self, db_session):
        results = get_policies(db_session, "azure", categories=["security"], mandatory_only=True)
        assert all(p["is_mandatory"] and p["category"] == "security" for p in results)


# ---------------------------------------------------------------------------
# get_approved_services
# ---------------------------------------------------------------------------

class TestGetApprovedServices:
    def test_returns_services_for_aws(self, db_session):
        results = get_approved_services(db_session, "aws")
        assert len(results) > 0
        assert all(s["csp"] == "aws" for s in results)

    def test_filters_by_capability_tag(self, db_session):
        results = get_approved_services(db_session, "aws", capability_tags=["containers"])
        assert len(results) > 0
        assert all(
            "containers" in [t.lower() for t in s["capability_tags"]]
            for s in results
        )

    def test_tag_matching_is_case_insensitive(self, db_session):
        lower = get_approved_services(db_session, "aws", capability_tags=["containers"])
        upper = get_approved_services(db_session, "aws", capability_tags=["CONTAINERS"])
        assert len(lower) == len(upper)

    def test_status_filter_approved(self, db_session):
        results = get_approved_services(db_session, "gcp", status="approved")
        assert all(s["status"] == "approved" for s in results)

    def test_status_filter_conditional(self, db_session):
        results = get_approved_services(db_session, "gcp", status="conditional")
        assert all(s["status"] == "conditional" for s in results)

    def test_result_has_required_fields(self, db_session):
        results = get_approved_services(db_session, "azure")
        required = {"service_name", "service_category", "capability_tags", "status"}
        assert required.issubset(results[0].keys())

    def test_unknown_csp_returns_empty(self, db_session):
        assert get_approved_services(db_session, "alibaba") == []

    def test_database_services_for_azure(self, db_session):
        results = get_approved_services(db_session, "azure", capability_tags=["relational"])
        assert len(results) > 0
        assert all("relational" in s["capability_tags"] for s in results)


# ---------------------------------------------------------------------------
# get_compliance_frameworks
# ---------------------------------------------------------------------------

class TestGetComplianceFrameworks:
    def test_returns_all_frameworks(self, db_session):
        results = get_compliance_frameworks(db_session)
        assert len(results) >= 5

    def test_filter_by_jurisdiction_us(self, db_session):
        results = get_compliance_frameworks(db_session, jurisdiction="US")
        assert len(results) > 0
        assert all(f["jurisdiction"] == "US" for f in results)

    def test_filter_by_jurisdiction_eu(self, db_session):
        results = get_compliance_frameworks(db_session, jurisdiction="EU")
        assert any(f["framework_code"] == "GDPR" for f in results)

    def test_filter_by_framework_codes(self, db_session):
        results = get_compliance_frameworks(db_session, framework_codes=["SOC2", "ISO27001"])
        codes = {f["framework_code"] for f in results}
        assert "SOC2" in codes
        assert "ISO27001" in codes

    def test_framework_codes_case_insensitive(self, db_session):
        lower = get_compliance_frameworks(db_session, framework_codes=["soc2"])
        upper = get_compliance_frameworks(db_session, framework_codes=["SOC2"])
        assert len(lower) == len(upper)

    def test_result_has_required_fields(self, db_session):
        results = get_compliance_frameworks(db_session)
        required = {"framework_code", "framework_name", "jurisdiction"}
        assert required.issubset(results[0].keys())

    def test_csp_param_does_not_break_query(self, db_session):
        # csp is accepted but currently unused for framework filtering
        results = get_compliance_frameworks(db_session, csp="aws")
        assert len(results) >= 5


# ---------------------------------------------------------------------------
# search_past_migrations
# ---------------------------------------------------------------------------

class TestSearchPastMigrations:
    def test_returns_migrations_for_aws(self, db_session):
        results = search_past_migrations(db_session, "aws")
        assert len(results) > 0
        assert all(m["csp"] == "aws" for m in results)

    def test_filter_by_archetype(self, db_session):
        results = search_past_migrations(db_session, "aws", app_archetype="web")
        assert len(results) > 0
        assert all(m["app_archetype"] == "web" for m in results)

    def test_filter_by_complexity_tier(self, db_session):
        results = search_past_migrations(db_session, "aws", complexity_tier="critical")
        assert len(results) > 0
        assert all(m["complexity_tier"] == "critical" for m in results)

    def test_keyword_search_source_pattern(self, db_session):
        results = search_past_migrations(db_session, "aws", keywords="VB6")
        assert len(results) > 0
        assert any("VB6" in m["source_pattern"] for m in results)

    def test_keyword_search_lessons_learned(self, db_session):
        results = search_past_migrations(db_session, "aws", keywords="Oracle")
        assert len(results) > 0

    def test_limit_respected(self, db_session):
        results = search_past_migrations(db_session, "aws", limit=2)
        assert len(results) <= 2

    def test_default_limit_is_five(self, db_session):
        results = search_past_migrations(db_session, "aws")
        assert len(results) <= 5

    def test_result_has_required_fields(self, db_session):
        results = search_past_migrations(db_session, "aws")
        required = {"source_pattern", "target_pattern", "app_archetype",
                    "complexity_tier", "duration_weeks", "lessons_learned"}
        assert required.issubset(results[0].keys())

    def test_unknown_csp_returns_empty(self, db_session):
        assert search_past_migrations(db_session, "alibaba") == []

    def test_archetype_and_complexity_combined(self, db_session):
        results = search_past_migrations(
            db_session, "aws", app_archetype="api", complexity_tier="high"
        )
        assert all(
            m["app_archetype"] == "api" and m["complexity_tier"] == "high"
            for m in results
        )

    def test_gcp_analytics_migrations(self, db_session):
        results = search_past_migrations(db_session, "gcp", app_archetype="analytics")
        assert len(results) > 0

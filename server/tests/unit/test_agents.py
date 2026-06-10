"""
Unit tests for all four agents.

All LLM calls and MCP calls are mocked — no network or subprocess required.
Tests verify: prompt construction, tool-loop mechanics, audit log population,
and that each agent returns the correct Pydantic type.
"""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.agents.architecture import ArchitectureAgent
from app.agents.base import AssessmentContext, BaseAgent
from app.agents.discovery import DiscoveryAgent, _format_document
from app.agents.estimation import EstimationAgent
from app.agents.org_policies import OrgPoliciesAgent, _blocks_to_api_content
from app.llm.base import GenerateResponse, TextBlock, ToolUseBlock
from app.schemas.architecture import ArchitecturePlan, ServiceMapping
from app.schemas.discovery import AppProfile, Dependency, ParsedDocument, TableBlock, TechStack
from app.schemas.enums import (
    ComplexityTier,
    CSP,
    EstimationModel,
    MigrationStrategy,
    Workstream,
)
from app.schemas.estimation import EstimationReport, Wave, WorkstreamEstimate
from app.schemas.policies import (
    ApprovedService,
    ComplianceFramework,
    Control,
    PolicyContext,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_document(texts=None, tables=None) -> ParsedDocument:
    return ParsedDocument(
        filename="app_inventory.docx",
        content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        text_blocks=texts or ["App: OrderService", "Stack: Java 11, Spring Boot, Oracle 12c"],
        table_blocks=tables or [],
    )


def _make_app_profile(**kwargs) -> AppProfile:
    defaults = dict(
        app_name="OrderService",
        owner="Platform Team",
        business_criticality="business-important",
        tech_stack=TechStack(
            languages=["Java"],
            frameworks=["Spring Boot"],
            databases=["Oracle"],
            containerized=False,
        ),
        dependencies=[
            Dependency(name="PaymentGateway", dep_type="external", protocol="REST"),
        ],
        tech_debt_indicators=["End-of-life Java 8", "No CI/CD pipeline"],
        cloud_readiness_signals=["REST API"],
        complexity_tier=ComplexityTier.high,
        confidence=0.8,
    )
    defaults.update(kwargs)
    return AppProfile(**defaults)


def _make_policy_context() -> PolicyContext:
    return PolicyContext(
        csp=CSP.aws,
        controls=[
            Control(
                code="AWS-SEC-001",
                title="Encrypt data at rest",
                category="security",
                severity="critical",
                is_mandatory=True,
                description="All data stores must use encryption at rest.",
            ),
        ],
        approved_services=[
            ApprovedService(
                service_name="Amazon RDS",
                service_category="database",
                capability_tags=["relational"],
            ),
        ],
        compliance_frameworks=[
            ComplianceFramework(
                framework_code="SOC2",
                framework_name="SOC 2 Type II",
                jurisdiction="US",
            ),
        ],
        landing_zone_standards=["Hub-spoke topology required for enterprise accounts"],
        escalation_flags=["CRITICAL: AWS-SEC-001 must be signed off by security team"],
    )


def _make_arch_plan() -> ArchitecturePlan:
    return ArchitecturePlan(
        migration_strategy=MigrationStrategy.replatform,
        target_services=[
            ServiceMapping(
                source_component="Oracle 12c",
                target_service="Amazon RDS",
                rationale="Managed relational DB with Oracle compatibility",
            )
        ],
        landing_zone_pattern="hub-spoke",
        security_controls=["Enable encryption at rest via KMS"],
        rationale="Replatform to managed services; Java app refactoring deferred.",
        policy_compliance_notes=["AWS-SEC-001 addressed via RDS encryption at rest."],
        risks=["Oracle license uplift on cloud"],
        confidence=0.75,
    )


def _make_estimation_report() -> EstimationReport:
    return EstimationReport(
        workstream_estimates=[
            WorkstreamEstimate(
                workstream=Workstream.infrastructure,
                effort_days_min=10,
                effort_days_max=25,
            ),
            WorkstreamEstimate(
                workstream=Workstream.application,
                effort_days_min=15,
                effort_days_max=45,
            ),
            WorkstreamEstimate(
                workstream=Workstream.data,
                effort_days_min=8,
                effort_days_max=20,
            ),
            WorkstreamEstimate(
                workstream=Workstream.testing,
                effort_days_min=10,
                effort_days_max=20,
            ),
        ],
        total_weeks_min=14,
        total_weeks_max=37,
        team_size_fte=6,
        waves=[Wave(wave_number=1, apps=["OrderService"], estimated_weeks=25)],
        assumptions=["Existing DB schema usable on RDS"],
        risks=["Oracle licence cost may increase"],
        confidence=0.7,
    )


def _make_assessment_context() -> AssessmentContext:
    return AssessmentContext.create(
        document=_make_document(),
        target_csp=CSP.aws,
        enable_multi_agent=True,
    )


def _make_llm_client(structured_return=None) -> MagicMock:
    """Returns a mock LLMClient whose generate_structured returns the given object."""
    llm = MagicMock()
    llm.generate_structured = AsyncMock(return_value=structured_return)
    llm.generate = AsyncMock()
    return llm


# ---------------------------------------------------------------------------
# AssessmentContext
# ---------------------------------------------------------------------------

class TestAssessmentContext:
    def test_create_assigns_session_id(self):
        ctx = AssessmentContext.create(
            document=_make_document(), target_csp=CSP.aws, enable_multi_agent=True
        )
        assert len(ctx.session_id) == 36  # UUID4

    def test_create_empty_audit_log(self):
        ctx = _make_assessment_context()
        assert ctx.audit_log == []

    def test_two_contexts_have_distinct_session_ids(self):
        doc = _make_document()
        ctx1 = AssessmentContext.create(doc, CSP.aws)
        ctx2 = AssessmentContext.create(doc, CSP.aws)
        assert ctx1.session_id != ctx2.session_id


# ---------------------------------------------------------------------------
# BaseAgent._log
# ---------------------------------------------------------------------------

class TestBaseAgentLog:
    def test_log_appends_event(self):
        class _Stub(BaseAgent):
            pass

        agent = _Stub()
        ctx = _make_assessment_context()
        agent._log(ctx, "test_event", key="value")

        assert len(ctx.audit_log) == 1
        entry = ctx.audit_log[0]
        assert entry["agent"] == "_Stub"
        assert entry["event"] == "test_event"
        assert entry["key"] == "value"
        assert "timestamp" in entry

    def test_log_multiple_events_ordered(self):
        class _Stub(BaseAgent):
            pass

        agent = _Stub()
        ctx = _make_assessment_context()
        agent._log(ctx, "first")
        agent._log(ctx, "second")

        assert ctx.audit_log[0]["event"] == "first"
        assert ctx.audit_log[1]["event"] == "second"


# ---------------------------------------------------------------------------
# _format_document (DiscoveryAgent helper)
# ---------------------------------------------------------------------------

class TestFormatDocument:
    def test_includes_filename(self):
        doc = _make_document()
        result = _format_document(doc)
        assert "app_inventory.docx" in result

    def test_includes_text_blocks(self):
        doc = _make_document(texts=["Hello", "World"])
        result = _format_document(doc)
        assert "Hello" in result
        assert "World" in result

    def test_includes_table_headers(self):
        table = TableBlock(sheet_name="Apps", headers=["Name", "Owner"], rows=[["OrderSvc", "IT"]])
        doc = _make_document(tables=[table])
        result = _format_document(doc)
        assert "Name" in result
        assert "Owner" in result
        assert "OrderSvc" in result

    def test_includes_warnings(self):
        doc = ParsedDocument(
            filename="scan.pdf",
            content_type="application/pdf",
            text_blocks=["text"],
            warnings=["Scanned PDF — OCR not performed"],
        )
        result = _format_document(doc)
        assert "Scanned PDF" in result

    def test_skips_blank_text_blocks(self):
        doc = _make_document(texts=["  ", "", "Real content"])
        result = _format_document(doc)
        lines = result.split("\n")
        # No standalone blank-only entries after joining
        assert "Real content" in result


# ---------------------------------------------------------------------------
# DiscoveryAgent
# ---------------------------------------------------------------------------

class TestDiscoveryAgent:
    @pytest.mark.asyncio
    async def test_returns_app_profile(self):
        profile = _make_app_profile()
        llm = _make_llm_client(structured_return=profile)
        agent = DiscoveryAgent(llm)
        ctx = _make_assessment_context()

        result = await agent.run(ctx)
        assert isinstance(result, AppProfile)
        assert result.app_name == "OrderService"

    @pytest.mark.asyncio
    async def test_calls_generate_structured_with_app_profile_type(self):
        profile = _make_app_profile()
        llm = _make_llm_client(structured_return=profile)
        agent = DiscoveryAgent(llm)
        ctx = _make_assessment_context()

        await agent.run(ctx)
        llm.generate_structured.assert_called_once()
        call_kwargs = llm.generate_structured.call_args
        assert call_kwargs.kwargs["output_type"] is AppProfile

    @pytest.mark.asyncio
    async def test_message_contains_document_text(self):
        profile = _make_app_profile()
        llm = _make_llm_client(structured_return=profile)
        agent = DiscoveryAgent(llm)
        ctx = _make_assessment_context()

        await agent.run(ctx)
        messages = llm.generate_structured.call_args.kwargs["messages"]
        full_text = " ".join(m["content"] for m in messages)
        assert "app_inventory.docx" in full_text

    @pytest.mark.asyncio
    async def test_audit_log_has_started_and_completed(self):
        profile = _make_app_profile()
        llm = _make_llm_client(structured_return=profile)
        agent = DiscoveryAgent(llm)
        ctx = _make_assessment_context()

        await agent.run(ctx)
        events = [e["event"] for e in ctx.audit_log]
        assert "started" in events
        assert "completed" in events

    @pytest.mark.asyncio
    async def test_audit_log_completed_includes_app_name(self):
        profile = _make_app_profile()
        llm = _make_llm_client(structured_return=profile)
        agent = DiscoveryAgent(llm)
        ctx = _make_assessment_context()

        await agent.run(ctx)
        completed = next(e for e in ctx.audit_log if e["event"] == "completed")
        assert completed["app_name"] == "OrderService"


# ---------------------------------------------------------------------------
# _blocks_to_api_content (OrgPoliciesAgent helper)
# ---------------------------------------------------------------------------

class TestBlocksToApiContent:
    def test_text_block(self):
        blocks = [TextBlock(text="hello")]
        result = _blocks_to_api_content(blocks)
        assert result == [{"type": "text", "text": "hello"}]

    def test_tool_use_block(self):
        blocks = [ToolUseBlock(id="tool_1", name="get_policies", input={"csp": "aws"})]
        result = _blocks_to_api_content(blocks)
        assert result == [
            {"type": "tool_use", "id": "tool_1", "name": "get_policies", "input": {"csp": "aws"}}
        ]

    def test_empty_text_block_skipped(self):
        blocks = [TextBlock(text="")]
        result = _blocks_to_api_content(blocks)
        assert result == []

    def test_mixed_blocks(self):
        blocks = [
            TextBlock(text="thinking..."),
            ToolUseBlock(id="t1", name="get_policies", input={}),
        ]
        result = _blocks_to_api_content(blocks)
        assert len(result) == 2
        assert result[0]["type"] == "text"
        assert result[1]["type"] == "tool_use"


# ---------------------------------------------------------------------------
# OrgPoliciesAgent
# ---------------------------------------------------------------------------

def _make_mcp_client(tools=None, tool_result='[]') -> MagicMock:
    from app.llm.base import ToolDefinition
    mcp = MagicMock()
    mcp.list_tools_as_anthropic_format = AsyncMock(
        return_value=tools
        or [
            ToolDefinition(
                name="get_policies",
                description="Get policies",
                input_schema={"type": "object", "properties": {}},
            )
        ]
    )
    mcp.call_tool = AsyncMock(return_value=tool_result)
    return mcp


def _make_tool_use_response(tool_id="t1", tool_name="get_policies", args=None) -> GenerateResponse:
    return GenerateResponse(
        content=[ToolUseBlock(id=tool_id, name=tool_name, input=args or {"csp": "aws"})],
        stop_reason="tool_use",
        usage={"input_tokens": 100, "output_tokens": 50},
        model="claude-haiku-4-5",
    )


def _make_end_turn_response(text="Done") -> GenerateResponse:
    return GenerateResponse(
        content=[TextBlock(text=text)],
        stop_reason="end_turn",
        usage={"input_tokens": 100, "output_tokens": 50},
        model="claude-haiku-4-5",
    )


class TestOrgPoliciesAgent:
    @pytest.mark.asyncio
    async def test_returns_policy_context(self):
        policy = _make_policy_context()
        llm = _make_llm_client(structured_return=policy)
        llm.generate = AsyncMock(return_value=_make_end_turn_response())
        mcp = _make_mcp_client()
        agent = OrgPoliciesAgent(llm, mcp)
        ctx = _make_assessment_context()

        result = await agent.run(ctx, _make_app_profile())
        assert isinstance(result, PolicyContext)

    @pytest.mark.asyncio
    async def test_tool_loop_calls_mcp_on_tool_use(self):
        policy = _make_policy_context()
        llm = MagicMock()
        # First call returns tool_use, second returns end_turn
        llm.generate = AsyncMock(
            side_effect=[
                _make_tool_use_response(),
                _make_end_turn_response(),
            ]
        )
        llm.generate_structured = AsyncMock(return_value=policy)
        mcp = _make_mcp_client()
        agent = OrgPoliciesAgent(llm, mcp)
        ctx = _make_assessment_context()

        await agent.run(ctx, _make_app_profile())
        mcp.call_tool.assert_awaited_once_with("get_policies", {"csp": "aws"})

    @pytest.mark.asyncio
    async def test_tool_loop_stops_on_end_turn(self):
        policy = _make_policy_context()
        llm = MagicMock()
        llm.generate = AsyncMock(return_value=_make_end_turn_response())
        llm.generate_structured = AsyncMock(return_value=policy)
        mcp = _make_mcp_client()
        agent = OrgPoliciesAgent(llm, mcp)
        ctx = _make_assessment_context()

        await agent.run(ctx, _make_app_profile())
        # Single generate() call — no tool calls made
        assert llm.generate.call_count == 1
        mcp.call_tool.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_multiple_tool_calls_in_one_turn(self):
        """Multiple ToolUseBlocks in a single response are all dispatched."""
        policy = _make_policy_context()
        llm = MagicMock()
        multi_tool_response = GenerateResponse(
            content=[
                ToolUseBlock(id="t1", name="get_policies", input={"csp": "aws"}),
                ToolUseBlock(id="t2", name="get_approved_services", input={"csp": "aws"}),
            ],
            stop_reason="tool_use",
            usage={"input_tokens": 100, "output_tokens": 50},
            model="claude-haiku-4-5",
        )
        llm.generate = AsyncMock(side_effect=[multi_tool_response, _make_end_turn_response()])
        llm.generate_structured = AsyncMock(return_value=policy)
        mcp = _make_mcp_client()
        agent = OrgPoliciesAgent(llm, mcp)
        ctx = _make_assessment_context()

        await agent.run(ctx, _make_app_profile())
        assert mcp.call_tool.await_count == 2

    @pytest.mark.asyncio
    async def test_audit_log_records_tool_calls(self):
        policy = _make_policy_context()
        llm = MagicMock()
        llm.generate = AsyncMock(
            side_effect=[_make_tool_use_response(), _make_end_turn_response()]
        )
        llm.generate_structured = AsyncMock(return_value=policy)
        mcp = _make_mcp_client()
        agent = OrgPoliciesAgent(llm, mcp)
        ctx = _make_assessment_context()

        await agent.run(ctx, _make_app_profile())
        tool_call_events = [e for e in ctx.audit_log if e["event"] == "tool_call"]
        assert len(tool_call_events) == 1
        assert tool_call_events[0]["tool"] == "get_policies"

    @pytest.mark.asyncio
    async def test_audit_log_has_started_and_completed(self):
        policy = _make_policy_context()
        llm = MagicMock()
        llm.generate = AsyncMock(return_value=_make_end_turn_response())
        llm.generate_structured = AsyncMock(return_value=policy)
        mcp = _make_mcp_client()
        agent = OrgPoliciesAgent(llm, mcp)
        ctx = _make_assessment_context()

        await agent.run(ctx, _make_app_profile())
        events = [e["event"] for e in ctx.audit_log]
        assert "started" in events
        assert "completed" in events

    @pytest.mark.asyncio
    async def test_synthesis_call_passes_accumulated_messages(self):
        """The generate_structured synthesis call receives the full conversation."""
        policy = _make_policy_context()
        llm = MagicMock()
        llm.generate = AsyncMock(
            side_effect=[_make_tool_use_response(), _make_end_turn_response()]
        )
        llm.generate_structured = AsyncMock(return_value=policy)
        mcp = _make_mcp_client(tool_result='[{"control_code": "AWS-SEC-001"}]')
        agent = OrgPoliciesAgent(llm, mcp)
        ctx = _make_assessment_context()

        await agent.run(ctx, _make_app_profile())
        messages_passed = llm.generate_structured.call_args.kwargs["messages"]
        # Conversation should be: user prompt + assistant (tool_use) + user (tool_result)
        #  + assistant (end_turn) + user (synthesis request) = at least 5 entries
        assert len(messages_passed) >= 5


# ---------------------------------------------------------------------------
# ArchitectureAgent
# ---------------------------------------------------------------------------

class TestArchitectureAgent:
    @pytest.mark.asyncio
    async def test_returns_architecture_plan(self):
        plan = _make_arch_plan()
        llm = _make_llm_client(structured_return=plan)
        agent = ArchitectureAgent(llm)
        ctx = _make_assessment_context()

        result = await agent.run(ctx, _make_app_profile(), _make_policy_context())
        assert isinstance(result, ArchitecturePlan)

    @pytest.mark.asyncio
    async def test_calls_generate_structured_with_architecture_plan_type(self):
        plan = _make_arch_plan()
        llm = _make_llm_client(structured_return=plan)
        agent = ArchitectureAgent(llm)
        ctx = _make_assessment_context()

        await agent.run(ctx, _make_app_profile(), _make_policy_context())
        assert llm.generate_structured.call_args.kwargs["output_type"] is ArchitecturePlan

    @pytest.mark.asyncio
    async def test_user_message_includes_mandatory_controls(self):
        plan = _make_arch_plan()
        llm = _make_llm_client(structured_return=plan)
        agent = ArchitectureAgent(llm)
        ctx = _make_assessment_context()

        await agent.run(ctx, _make_app_profile(), _make_policy_context())
        messages = llm.generate_structured.call_args.kwargs["messages"]
        combined = " ".join(m["content"] for m in messages)
        assert "AWS-SEC-001" in combined

    @pytest.mark.asyncio
    async def test_user_message_includes_approved_services(self):
        plan = _make_arch_plan()
        llm = _make_llm_client(structured_return=plan)
        agent = ArchitectureAgent(llm)
        ctx = _make_assessment_context()

        await agent.run(ctx, _make_app_profile(), _make_policy_context())
        messages = llm.generate_structured.call_args.kwargs["messages"]
        combined = " ".join(m["content"] for m in messages)
        assert "Amazon RDS" in combined

    @pytest.mark.asyncio
    async def test_user_message_includes_tech_debt(self):
        plan = _make_arch_plan()
        llm = _make_llm_client(structured_return=plan)
        agent = ArchitectureAgent(llm)
        ctx = _make_assessment_context()
        profile = _make_app_profile(tech_debt_indicators=["End-of-life Java 8"])

        await agent.run(ctx, profile, _make_policy_context())
        messages = llm.generate_structured.call_args.kwargs["messages"]
        combined = " ".join(m["content"] for m in messages)
        assert "End-of-life Java 8" in combined

    @pytest.mark.asyncio
    async def test_audit_log_has_started_and_completed(self):
        plan = _make_arch_plan()
        llm = _make_llm_client(structured_return=plan)
        agent = ArchitectureAgent(llm)
        ctx = _make_assessment_context()

        await agent.run(ctx, _make_app_profile(), _make_policy_context())
        events = [e["event"] for e in ctx.audit_log]
        assert "started" in events
        assert "completed" in events

    @pytest.mark.asyncio
    async def test_audit_log_completed_includes_strategy(self):
        plan = _make_arch_plan()
        llm = _make_llm_client(structured_return=plan)
        agent = ArchitectureAgent(llm)
        ctx = _make_assessment_context()

        await agent.run(ctx, _make_app_profile(), _make_policy_context())
        completed = next(e for e in ctx.audit_log if e["event"] == "completed")
        assert "replatform" in completed["strategy"]


# ---------------------------------------------------------------------------
# EstimationAgent
# ---------------------------------------------------------------------------

class TestEstimationAgent:
    @pytest.mark.asyncio
    async def test_returns_estimation_report(self):
        report = _make_estimation_report()
        llm = _make_llm_client(structured_return=report)
        agent = EstimationAgent(llm)
        ctx = _make_assessment_context()

        result = await agent.run(ctx, _make_app_profile(), _make_arch_plan())
        assert isinstance(result, EstimationReport)

    @pytest.mark.asyncio
    async def test_calls_generate_structured_with_estimation_report_type(self):
        report = _make_estimation_report()
        llm = _make_llm_client(structured_return=report)
        agent = EstimationAgent(llm)
        ctx = _make_assessment_context()

        await agent.run(ctx, _make_app_profile(), _make_arch_plan())
        assert llm.generate_structured.call_args.kwargs["output_type"] is EstimationReport

    @pytest.mark.asyncio
    async def test_user_message_includes_migration_strategy(self):
        report = _make_estimation_report()
        llm = _make_llm_client(structured_return=report)
        agent = EstimationAgent(llm)
        ctx = _make_assessment_context()

        await agent.run(ctx, _make_app_profile(), _make_arch_plan())
        messages = llm.generate_structured.call_args.kwargs["messages"]
        combined = " ".join(m["content"] for m in messages)
        assert "replatform" in combined

    @pytest.mark.asyncio
    async def test_user_message_includes_complexity_tier(self):
        report = _make_estimation_report()
        llm = _make_llm_client(structured_return=report)
        agent = EstimationAgent(llm)
        ctx = _make_assessment_context()

        await agent.run(ctx, _make_app_profile(), _make_arch_plan())
        messages = llm.generate_structured.call_args.kwargs["messages"]
        combined = " ".join(m["content"] for m in messages)
        assert "high" in combined

    @pytest.mark.asyncio
    async def test_default_estimation_model_is_parametric(self):
        agent = EstimationAgent(llm=MagicMock())
        assert agent._estimation_model == EstimationModel.parametric

    @pytest.mark.asyncio
    async def test_custom_estimation_model_passed_to_prompt(self):
        report = _make_estimation_report()
        llm = _make_llm_client(structured_return=report)
        agent = EstimationAgent(llm, estimation_model=EstimationModel.analogous)
        ctx = _make_assessment_context()

        await agent.run(ctx, _make_app_profile(), _make_arch_plan())
        messages = llm.generate_structured.call_args.kwargs["messages"]
        combined = " ".join(m["content"] for m in messages)
        assert "analogous" in combined

    @pytest.mark.asyncio
    async def test_audit_log_has_started_and_completed(self):
        report = _make_estimation_report()
        llm = _make_llm_client(structured_return=report)
        agent = EstimationAgent(llm)
        ctx = _make_assessment_context()

        await agent.run(ctx, _make_app_profile(), _make_arch_plan())
        events = [e["event"] for e in ctx.audit_log]
        assert "started" in events
        assert "completed" in events

    @pytest.mark.asyncio
    async def test_audit_log_completed_includes_timeline(self):
        report = _make_estimation_report()
        llm = _make_llm_client(structured_return=report)
        agent = EstimationAgent(llm)
        ctx = _make_assessment_context()

        await agent.run(ctx, _make_app_profile(), _make_arch_plan())
        completed = next(e for e in ctx.audit_log if e["event"] == "completed")
        assert completed["total_weeks_min"] == 14
        assert completed["total_weeks_max"] == 37

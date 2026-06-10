"""
OrgPoliciesAgent — fetches org policies via MCP tools and synthesises a
structured PolicyContext.

Two-phase design:
  Phase 1  Tool-use loop — Claude calls MCP tools to retrieve policies,
           approved services, compliance frameworks, and past migrations
           relevant to the target CSP and app profile.
  Phase 2  Structured synthesis — a second generate_structured() call maps
           the accumulated tool results into a validated PolicyContext.

Thinking is disabled in Phase 1 (tool loop) for speed; the synthesis
call inherits the provider default.
"""
from ..llm.base import LLMClient, TextBlock, ThinkingBlock, ToolUseBlock
from ..mcp.client import MCPClient
from ..schemas.discovery import AppProfile
from ..schemas.enums import CSP
from ..schemas.policies import (
    ApprovedService,
    ComplianceFramework,
    Control,
    PolicyContext,
)
from .base import AssessmentContext, BaseAgent

_MAX_TOOL_TURNS = 10

_TOOL_LOOP_SYSTEM = """\
You are an org policies specialist for cloud migrations. Use the available tools
to gather all policy data required for the migration described below.

Required tool calls (make all of them):
1. get_policies          — fetch mandatory controls for the target CSP
2. get_approved_services — fetch approved services relevant to the workload
3. get_compliance_frameworks — fetch applicable compliance frameworks
4. search_past_migrations — find analogous past migrations for context

Call each tool with the most specific parameters you can infer from the app
profile. For example, if the app has databases, include "relational" or "nosql"
in capability_tags for get_approved_services.

Continue until you have called all four tools at least once, then stop.
"""

_SYNTHESIS_SYSTEM = """\
You are an org policies specialist. Given the tool results in the conversation,
produce a structured PolicyContext containing:

controls            — all mandatory policies retrieved, mapped to Control schema
approved_services   — approved services retrieved, mapped to ApprovedService schema
compliance_frameworks — compliance frameworks retrieved, mapped to ComplianceFramework schema
landing_zone_standards — extract any landing zone rules from the policy descriptions
escalation_flags    — list any CRITICAL severity controls or compliance requirements
                     that the architecture team must explicitly address
csp                 — the target cloud provider

Only include items that were actually returned by the tools. Do not invent data.
"""


def _build_tool_loop_prompt(csp: CSP, app_profile: AppProfile) -> str:
    tech = app_profile.tech_stack
    parts = [
        f"Target CSP: {csp}",
        f"Application: {app_profile.app_name}",
        f"Complexity tier: {app_profile.complexity_tier}",
        f"Business criticality: {app_profile.business_criticality or 'unknown'}",
    ]
    if tech.languages:
        parts.append(f"Languages: {', '.join(tech.languages)}")
    if tech.databases:
        parts.append(f"Databases: {', '.join(tech.databases)}")
    if tech.containerized:
        parts.append("Containerized: yes")
    if app_profile.data_residency_constraints:
        parts.append(
            "Data residency constraints: " + "; ".join(app_profile.data_residency_constraints)
        )
    if app_profile.tech_debt_indicators:
        parts.append(
            "Tech debt indicators: " + "; ".join(app_profile.tech_debt_indicators[:5])
        )
    parts.append(
        "\nFetch all relevant policies, approved services, compliance frameworks, "
        "and past migration patterns for this workload."
    )
    return "\n".join(parts)


def _blocks_to_api_content(blocks: list) -> list[dict]:
    """Convert normalised ContentBlocks back to Anthropic API content dicts."""
    result = []
    for block in blocks:
        if isinstance(block, TextBlock) and block.text:
            result.append({"type": "text", "text": block.text})
        elif isinstance(block, ToolUseBlock):
            result.append(
                {
                    "type": "tool_use",
                    "id": block.id,
                    "name": block.name,
                    "input": block.input,
                }
            )
        elif isinstance(block, ThinkingBlock) and block.thinking:
            result.append({"type": "thinking", "thinking": block.thinking})
    return result


class OrgPoliciesAgent(BaseAgent):
    """Fetches org policies via MCP tools and returns a PolicyContext."""

    def __init__(self, llm: LLMClient, mcp_client: MCPClient) -> None:
        self._llm = llm
        self._mcp = mcp_client

    async def run(self, ctx: AssessmentContext, app_profile: AppProfile) -> PolicyContext:
        tools = await self._mcp.list_tools_as_anthropic_format()
        self._log(
            ctx,
            "started",
            csp=str(ctx.target_csp),
            available_tools=[t.name for t in tools],
        )

        messages: list[dict] = [
            {
                "role": "user",
                "content": _build_tool_loop_prompt(ctx.target_csp, app_profile),
            }
        ]

        tool_calls_made: list[str] = []

        # Phase 1: Tool-use loop — thinking disabled for speed in fetch loops
        for turn in range(_MAX_TOOL_TURNS):
            response = await self._llm.generate(
                messages=messages,
                system=_TOOL_LOOP_SYSTEM,
                tools=tools,
                thinking=False,
            )

            messages.append(
                {"role": "assistant", "content": _blocks_to_api_content(response.content)}
            )

            if response.stop_reason != "tool_use":
                self._log(ctx, "tool_loop_ended", turns=turn + 1, stop_reason=response.stop_reason)
                break

            tool_results: list[dict] = []
            for block in response.content:
                if isinstance(block, ToolUseBlock):
                    result_text = await self._mcp.call_tool(block.name, block.input, ctx)
                    tool_calls_made.append(block.name)
                    tool_results.append(
                        {
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": result_text,
                        }
                    )

            messages.append({"role": "user", "content": tool_results})

        # Phase 2: Structured synthesis from accumulated tool results
        messages.append(
            {
                "role": "user",
                "content": (
                    "All tool calls are complete. Now produce the final PolicyContext JSON "
                    "based strictly on the data returned by the tools above."
                ),
            }
        )

        policy_context = await self._llm.generate_structured(
            messages=messages,
            output_type=PolicyContext,
            system=_SYNTHESIS_SYSTEM,
        )

        self._log(
            ctx,
            "completed",
            tool_calls=tool_calls_made,
            controls=len(policy_context.controls),
            approved_services=len(policy_context.approved_services),
            frameworks=len(policy_context.compliance_frameworks),
            escalation_flags=policy_context.escalation_flags,
        )
        return policy_context

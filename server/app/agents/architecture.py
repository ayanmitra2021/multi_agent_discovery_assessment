"""
ArchitectureAgent — recommends a target-state architecture given the
AppProfile (from Discovery) and PolicyContext (from OrgPolicies).

The agent uses generate_structured() to produce an ArchitecturePlan that:
  - Selects a migration strategy aligned with complexity, criticality, and debt
  - Maps source components to approved target services only
  - Applies mandatory security controls as baseline
  - Flags any policy compliance gaps
"""
from ..llm.base import LLMClient
from ..schemas.architecture import ArchitecturePlan
from ..schemas.discovery import AppProfile
from ..schemas.policies import PolicyContext
from .base import AssessmentContext, BaseAgent

_SYSTEM_PROMPT = """\
You are a cloud migration architect. Given an application profile and the
organisation's policy context, produce a target-state architecture plan.

## Migration strategy selection

Choose ONE of: rehost | replatform | refactor | replace | retire

Heuristics:
  rehost     — high criticality + low change tolerance + time-constrained;
               minimal code change, lift-and-shift to IaaS/VMs
  replatform — moderate tech debt, some modernisation acceptable;
               move to managed services (PaaS) without full rewrite
  refactor   — high cloud readiness, modern stack, strategic priority;
               redesign for cloud-native (containers, serverless, microservices)
  replace    — COTS SaaS replacement is cheaper than migration;
               decommission and adopt cloud-native equivalent
  retire     — application sunset planned, no active users, or superseded

## Service mapping

Map each significant source component (web tier, app tier, database, cache,
messaging, etc.) to a target cloud service.
IMPORTANT: Only use services from the approved_services list provided.
Avoid any service with status=deprecated.
If a required capability has no approved service, note it in policy_compliance_notes.

## Landing zone pattern

Choose ONE of: hub-spoke | standalone | shared-services
  hub-spoke      — large enterprise, centralised egress and security services
  standalone     — single-team, self-contained, simpler governance
  shared-services — shared platform team managing common infra

## Security controls

Start with ALL mandatory controls from the policy context (is_mandatory=true).
Add relevant recommended controls based on the app's risk profile.
List each as a short action statement, e.g. "Enable encryption at rest using KMS".

## Policy compliance notes

For every mandatory control, confirm it is addressed by the architecture, OR
flag it as a gap with: "GAP: [control_code] — [reason not addressed]".

## Risks

List 3-8 migration risks specific to this application, e.g.:
  "Oracle licence cost increase on cloud", "Session state in-memory — requires
  sticky sessions or externalisation before migration"

## Confidence

Float 0.0–1.0. Lower when policy context is sparse or app profile has low confidence.
"""


def _build_user_prompt(ctx: AssessmentContext, app: AppProfile, policy: PolicyContext) -> str:
    tech = app.tech_stack
    lines = [
        "# Application Profile",
        f"Name: {app.app_name}",
        f"Owner: {app.owner or 'unknown'}",
        f"Business criticality: {app.business_criticality or 'unknown'}",
        f"Complexity tier: {app.complexity_tier}",
        f"Confidence: {app.confidence}",
        "",
        "## Tech stack",
        f"Languages: {', '.join(tech.languages) or 'not specified'}",
        f"Frameworks: {', '.join(tech.frameworks) or 'none'}",
        f"Databases: {', '.join(tech.databases) or 'none'}",
        f"OS/Platform: {tech.os_platform or 'not specified'}",
        f"Containerized: {tech.containerized}",
    ]
    if app.dependencies:
        lines += ["", "## Dependencies"]
        for dep in app.dependencies:
            proto = f" ({dep.protocol})" if dep.protocol else ""
            lines.append(f"  - {dep.name}{proto} [{dep.dep_type}]")
    if app.tech_debt_indicators:
        lines += ["", "## Tech debt indicators"]
        lines += [f"  - {d}" for d in app.tech_debt_indicators]
    if app.cloud_readiness_signals:
        lines += ["", "## Cloud readiness signals"]
        lines += [f"  - {s}" for s in app.cloud_readiness_signals]
    if app.data_residency_constraints:
        lines += ["", "## Data residency constraints"]
        lines += [f"  - {c}" for c in app.data_residency_constraints]

    lines += [
        "",
        "# Policy Context",
        f"Target CSP: {policy.csp}",
        "",
        "## Mandatory controls",
    ]
    mandatory = [c for c in policy.controls if c.is_mandatory]
    for ctrl in mandatory:
        lines.append(f"  [{ctrl.code}] {ctrl.title} (severity: {ctrl.severity})")
        lines.append(f"    {ctrl.description}")

    if policy.approved_services:
        lines += ["", "## Approved services"]
        for svc in policy.approved_services:
            tags = ", ".join(svc.capability_tags)
            lines.append(f"  - {svc.service_name} [{svc.service_category}] tags: {tags}")
            if svc.constraints_note:
                lines.append(f"    note: {svc.constraints_note}")

    if policy.compliance_frameworks:
        lines += ["", "## Applicable compliance frameworks"]
        for fw in policy.compliance_frameworks:
            lines.append(f"  - {fw.framework_code}: {fw.framework_name} ({fw.jurisdiction})")

    if policy.landing_zone_standards:
        lines += ["", "## Landing zone standards"]
        lines += [f"  - {s}" for s in policy.landing_zone_standards]

    if policy.escalation_flags:
        lines += ["", "## Escalation flags (must address)"]
        lines += [f"  - {f}" for f in policy.escalation_flags]

    return "\n".join(lines)


class ArchitectureAgent(BaseAgent):
    """Recommends target-state architecture given AppProfile and PolicyContext."""

    def __init__(self, llm: LLMClient) -> None:
        self._llm = llm

    async def run(
        self,
        ctx: AssessmentContext,
        app_profile: AppProfile,
        policy_context: PolicyContext,
    ) -> ArchitecturePlan:
        self._log(
            ctx,
            "started",
            app_name=app_profile.app_name,
            complexity_tier=str(app_profile.complexity_tier),
            csp=str(ctx.target_csp),
        )

        messages = [
            {"role": "user", "content": _build_user_prompt(ctx, app_profile, policy_context)}
        ]

        plan = await self._llm.generate_structured(
            messages=messages,
            output_type=ArchitecturePlan,
            system=_SYSTEM_PROMPT,
        )

        self._log(
            ctx,
            "completed",
            strategy=str(plan.migration_strategy),
            landing_zone=plan.landing_zone_pattern,
            services_mapped=len(plan.target_services),
            risks=len(plan.risks),
            confidence=plan.confidence,
        )
        return plan

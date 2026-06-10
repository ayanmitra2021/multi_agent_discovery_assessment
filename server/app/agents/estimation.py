"""
EstimationAgent — produces workstream effort estimates and wave groupings
given the AppProfile and ArchitecturePlan.

Uses generate_structured() to return a validated EstimationReport with
min/max day estimates per workstream and risk-adjusted timeline.
"""
from ..llm.base import LLMClient
from ..schemas.architecture import ArchitecturePlan
from ..schemas.discovery import AppProfile
from ..schemas.estimation import EstimationReport
from ..schemas.enums import EstimationModel
from .base import AssessmentContext, BaseAgent

_SYSTEM_PROMPT = """\
You are a cloud migration estimation specialist. Given an application profile and
architecture plan, produce effort estimates and a migration timeline.

## Workstreams (estimate ALL four)

infrastructure — cloud infra setup, IaC, networking, landing zone, IAM
application    — code changes, configuration, CI/CD pipeline, containerisation
data           — data migration, schema changes, cutover, validation
testing        — functional, integration, performance, security testing

## Baseline sizing (effort_days_min to effort_days_max per workstream)

Strategy | infra       | application | data        | testing
---------|-------------|-------------|-------------|----------
rehost   | 5  – 15     | 2  – 5      | 3  – 10     |  5 – 10
replatform| 10 – 25    | 10 – 30     | 5  – 20     | 10 – 20
refactor | 15 – 30     | 30 – 90     | 10 – 30     | 20 – 40
replace  |  5 – 10     |  2 – 5      |  5 – 20     |  5 – 15
retire   |  1 – 3      |  0 – 2      |  0 – 5      |  1 – 3

## Complexity multipliers (apply to ALL workstreams)

low      = 0.7×
medium   = 1.0×
high     = 1.5×
critical = 2.5×

## Additional adjustments

tech_debt_indicators  — each indicator adds ~10% to the application workstream
external dependencies — each adds 3-5 days to the data + testing workstreams
containerized=false   — add 5-10 days to the application workstream (Dockerisation)
data_residency        — each constraint adds 3-7 days to data + testing workstreams

## Totals

total_weeks_min = ceil(sum(effort_days_min for all workstreams) / 5 / team_size_fte)
total_weeks_max = ceil(sum(effort_days_max for all workstreams) / 5 / team_size_fte)
team_size_fte   — 4 for low/medium, 6 for high, 8 for critical

## Wave planning

Group apps into waves based on risk and dependencies.
Wave 1 = low-risk pilot (rehost or simple replatform candidates)
Wave 2 = main migration body
Wave 3 = complex / critical apps last

For a single application, produce one wave with rationale.

## Assumptions and risks

List 3-6 assumptions (e.g. "Existing CI/CD pipeline will be reused").
List 3-6 risks (e.g. "Oracle licence cost may increase on cloud").

## Confidence

Float 0.0–1.0. Lower when the app profile has missing tech stack details or
the document was sparse.
"""


def _build_user_prompt(
    ctx: AssessmentContext,
    app: AppProfile,
    plan: ArchitecturePlan,
    estimation_model: EstimationModel,
) -> str:
    tech = app.tech_stack
    lines = [
        "# Application Profile",
        f"Name: {app.app_name}",
        f"Business criticality: {app.business_criticality or 'unknown'}",
        f"Complexity tier: {app.complexity_tier}",
        f"Confidence: {app.confidence}",
        f"Containerized: {tech.containerized}",
        f"Languages: {', '.join(tech.languages) or 'not specified'}",
        f"Databases: {', '.join(tech.databases) or 'none'}",
        f"External dependencies: {len([d for d in app.dependencies if d.dep_type in ('external', 'third-party')])}",
        f"Tech debt indicators ({len(app.tech_debt_indicators)}): "
        + ("; ".join(app.tech_debt_indicators[:6]) or "none"),
        f"Data residency constraints: {len(app.data_residency_constraints)}",
        "",
        "# Architecture Plan",
        f"Migration strategy: {plan.migration_strategy}",
        f"Landing zone: {plan.landing_zone_pattern}",
        f"Target services mapped: {len(plan.target_services)}",
        f"Risks identified: {len(plan.risks)}",
    ]
    if plan.risks:
        lines += ["", "Architecture risks:"]
        lines += [f"  - {r}" for r in plan.risks]
    lines += [
        "",
        f"Estimation model: {estimation_model}",
        "",
        "Produce the EstimationReport JSON based on the above.",
    ]
    return "\n".join(lines)


class EstimationAgent(BaseAgent):
    """Produces workstream effort estimates and migration waves."""

    def __init__(self, llm: LLMClient, estimation_model: EstimationModel = EstimationModel.parametric) -> None:
        self._llm = llm
        self._estimation_model = estimation_model

    async def run(
        self,
        ctx: AssessmentContext,
        app_profile: AppProfile,
        arch_plan: ArchitecturePlan,
    ) -> EstimationReport:
        self._log(
            ctx,
            "started",
            app_name=app_profile.app_name,
            strategy=str(arch_plan.migration_strategy),
            estimation_model=str(self._estimation_model),
        )

        messages = [
            {
                "role": "user",
                "content": _build_user_prompt(ctx, app_profile, arch_plan, self._estimation_model),
            }
        ]

        report = await self._llm.generate_structured(
            messages=messages,
            output_type=EstimationReport,
            system=_SYSTEM_PROMPT,
        )

        self._log(
            ctx,
            "completed",
            total_weeks_min=report.total_weeks_min,
            total_weeks_max=report.total_weeks_max,
            team_size_fte=report.team_size_fte,
            waves=len(report.waves),
            confidence=report.confidence,
        )
        return report

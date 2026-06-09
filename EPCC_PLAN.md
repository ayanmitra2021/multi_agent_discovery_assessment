# Plan: Multi-Agent Cloud Migration Assessment — Backend

**Created**: 2026-06-09 | **Effort**: ~26h | **Complexity**: Complex

---

## 1. Objective

**Goal**: Build a Python/FastAPI backend that accepts a portfolio document + target CSP and runs a four-agent Claude Agentic SDK pipeline (Discovery, Org Policies, Architecture, Estimation) to produce a structured migration assessment report.

**Why**: The frontend intake form is complete; the backend is the core intelligence of the product — without it there is no assessment.

**Success criteria**:
- `POST /api/assess` accepts a file + CSP and returns a full `AssessmentReport` JSON
- Discovery and Org Policies agents run in parallel via `asyncio.gather()`; Architecture waits for both
- Org Policies Agent retrieves data exclusively via MCP tools backed by a seeded SQLite policy store
- Every agent decision is persisted to an audit trail keyed by `assessment_id`
- Switching `LLM_PROVIDER` (claude/openai/gemini) requires only an env-var change

---

## 2. Approach

### Directory layout (`server/`)

```
server/
├── app/
│   ├── main.py                  # FastAPI factory + lifespan
│   ├── config.py                # pydantic-settings from .env
│   ├── deps.py                  # DI: orchestrator, llm client, stores
│   ├── api/
│   │   ├── routes_assess.py     # POST /api/assess
│   │   ├── routes_health.py     # GET /health
│   │   └── errors.py
│   ├── schemas/                 # Pydantic contracts (api, discovery, policies,
│   │                            #   architecture, estimation, report, enums)
│   ├── ingestion/               # parser.py + extractors/ (pdf, docx, xlsx, csv)
│   ├── llm/                     # base protocol, factory, providers/
│   ├── context.py               # AssessmentContext dataclass (replaces LangGraph state)
│   ├── orchestrator.py          # CloudMigrationOrchestrator class
│   ├── agents/                  # base, discovery, policies, architecture, estimation
│   ├── mcp/
│   │   ├── client.py            # MCPClient wrapper (used by Policies Agent)
│   │   └── server/              # server.py, tools.py, repository.py
│   ├── audit/                   # trail.py, events.py
│   └── persistence/             # policies_db.py, audit_db.py, seed/
├── data/                        # policies.sqlite, audit.sqlite
├── tests/                       # unit/, integration/, fixtures/
├── pyproject.toml
└── .env.example
```

### Pipeline flow

```
POST /api/assess
    │
    ▼
DocumentParser (bytes → ParsedDocument)
    │
    ▼
CloudMigrationOrchestrator.run(AssessmentContext seed)
    │
    ├──────────────────────────────────────────┐
    ▼                                          ▼
DiscoveryAgent.run()                  OrgPoliciesAgent.run()    ← asyncio.gather()
(AppProfile via                       (PolicyContext via
 claude-opus-4-8 + tool use)           claude-opus-4-8 + MCP tools)
    │                                          │
    └──────────────────┬───────────────────────┘
                       ▼
              ArchitectureAgent.run()           ← awaits both
              (ArchitecturePlan)
                       │
                       ▼
              EstimationAgent.run()
              (EstimationReport)
                       │
                       ▼
              compose_report() → AssessmentReport
                       │
                       ▼
              AssessResponse (JSON)
```

### Key technology decisions

| Decision | Choice | Rationale |
|---|---|---|
| Orchestration | Custom `CloudMigrationOrchestrator` Python class | No framework overhead; `asyncio.gather()` handles parallelism natively; explicit and debuggable |
| Agent LLM calls | `anthropic.AsyncAnthropic().messages.create()` with tool use | Primary SDK; `claude-opus-4-8` with `thinking: {type: "adaptive"}` for complex reasoning |
| Structured agent output | `output_config: {format: {type: "json_schema", ...}}` + Pydantic | Replaces prefills (not supported on 4.8); guaranteed valid JSON, validated by `messages.parse()` |
| Agentic loop | SDK tool runner (`client.beta.messages.toolRunner()`) or manual loop | Tool runner for simple agents; manual loop for Policies Agent (need to intercept MCP calls) |
| LLM abstraction | `LLMClient` Protocol + factory | Agents depend on protocol; switching provider = env-var change |
| MCP transport | In-process STDIO for MVP | Zero extra process management; MCP tools exposed as Anthropic tool format via `anthropic.lib.tools.mcp` |
| Policy store | SQLite + SQLAlchemy | Zero-setup for dev; swap to Postgres by changing one env var |
| State container | `AssessmentContext` Python dataclass | Plain Python; no framework-managed state graph; explicitly passed between agents |
| Report format | JSON + Markdown (MVP); DOCX optional | Fastest to ship; frontend can render immediately |
| Parallelism | `asyncio.gather(discovery.run(ctx), policies.run(ctx))` | Python built-in; no extra dependency; `return_exceptions=True` for graceful degradation |

### `AssessmentContext` shape (replaces LangGraph `AssessmentState`)

```python
@dataclasses.dataclass
class AssessmentContext:
    # Seeded inputs (read-only)
    assessment_id: str
    target_csp: str
    parsed_document: ParsedDocument

    # Written by each agent
    app_profile: Optional[AppProfile] = None
    policy_context: Optional[PolicyContext] = None
    architecture_plan: Optional[ArchitecturePlan] = None
    estimation_report: Optional[EstimationReport] = None
    report: Optional[AssessmentReport] = None

    # Accumulated across all agents
    audit_events: list[AuditEvent] = dataclasses.field(default_factory=list)
    errors: list[str] = dataclasses.field(default_factory=list)
    status: str = "running"  # running | completed | partial | failed
```

### Orchestrator pattern

```python
class CloudMigrationOrchestrator:
    def __init__(self, client: anthropic.AsyncAnthropic, mcp_client: MCPClient):
        self.discovery = DiscoveryAgent(client)
        self.policies = OrgPoliciesAgent(client, mcp_client)
        self.architecture = ArchitectureAgent(client)
        self.estimation = EstimationAgent(client)

    async def run(self, doc: ParsedDocument, csp: str) -> AssessmentReport:
        ctx = AssessmentContext(assessment_id=uuid4().hex, target_csp=csp,
                                parsed_document=doc)
        # Phase 1: parallel
        results = await asyncio.gather(
            self.discovery.run(ctx),
            self.policies.run(ctx),
            return_exceptions=True,
        )
        ctx.app_profile = results[0] if not isinstance(results[0], Exception) else None
        ctx.policy_context = results[1] if not isinstance(results[1], Exception) else None
        if isinstance(results[0], Exception):
            ctx.errors.append(f"Discovery failed: {results[0]}")
        if isinstance(results[1], Exception):
            ctx.errors.append(f"OrgPolicies failed: {results[1]}")

        # Phase 2: sequential
        ctx.architecture_plan = await self.architecture.run(ctx)
        ctx.estimation_report = await self.estimation.run(ctx)
        ctx.report = compose_report(ctx)
        ctx.status = "partial" if ctx.errors else "completed"
        return ctx.report
```

### Agent pattern (Discovery and Architecture)

Each agent calls `claude-opus-4-8` via the Anthropic SDK with structured outputs:

```python
class DiscoveryAgent(BaseAgent):
    SYSTEM = "You are a cloud migration technical analyst..."

    async def run(self, ctx: AssessmentContext) -> AppProfile:
        self._emit_audit(ctx, "discovery_start")
        response = await self.client.messages.parse(
            model="claude-opus-4-8",
            max_tokens=8192,
            thinking={"type": "adaptive"},
            system=self.SYSTEM,
            output_config={"format": {"type": "json_schema",
                                      "schema": AppProfile.model_json_schema()}},
            messages=[{"role": "user",
                        "content": format_discovery_prompt(ctx.parsed_document)}],
        )
        self._emit_audit(ctx, "discovery_complete", tokens=response.usage)
        return AppProfile.model_validate(response.parsed_output)
```

### Org Policies Agent pattern (with MCP)

The Policies Agent runs Claude with the MCP server's tools in a tool-use loop:

```python
class OrgPoliciesAgent(BaseAgent):
    SYSTEM = "You are a cloud policy advisor..."

    def __init__(self, client, mcp_client: MCPClient):
        super().__init__(client)
        self.mcp_client = mcp_client

    async def run(self, ctx: AssessmentContext) -> PolicyContext:
        # Get MCP tools in Anthropic format
        mcp_tools = await self.mcp_client.list_tools_as_anthropic_format()
        messages = [{"role": "user",
                     "content": f"Fetch policies for {ctx.target_csp}..."}]
        # Manual tool-use loop (MCP calls are intercepted here)
        while True:
            response = await self.client.messages.create(
                model="claude-opus-4-8",
                max_tokens=8192,
                system=self.SYSTEM,
                tools=mcp_tools,
                messages=messages,
            )
            if response.stop_reason == "end_turn":
                break
            # Execute MCP tool calls
            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    result = await self.mcp_client.call_tool(block.name, block.input)
                    tool_results.append({"type": "tool_result",
                                         "tool_use_id": block.id, "content": result})
                    self._emit_audit(ctx, f"mcp_tool_{block.name}")
            messages.append({"role": "assistant", "content": response.content})
            messages.append({"role": "user", "content": tool_results})
        return self._parse_policy_context(response, ctx)
```

### Policies DB schema (SQLite)

```
policies             (id, csp, control_code, title, category, severity,
                      is_mandatory, description, source_ref)
approved_services    (id, csp, service_name, service_category,
                      capability_tags, status, constraints_note)
compliance_frameworks(id, framework_code, framework_name, jurisdiction, version)
framework_controls   (id, framework_id→, policy_id→, mapping_note)
past_migrations      (id, csp, source_pattern, target_pattern, app_archetype,
                      complexity_tier, outcome, duration_weeks, lessons_learned)
```

### MCP tool signatures (read-only)

```python
get_policies(csp, categories=None, mandatory_only=False) → list[Control]
get_approved_services(csp, capability_tags=None, status="approved") → list[ApprovedService]
get_compliance_frameworks(csp=None, jurisdiction=None, framework_codes=None) → list[ComplianceFramework]
search_past_migrations(csp, app_archetype=None, complexity_tier=None, keywords=None, limit=5) → list[PastMigrationPattern]
```

### `pyproject.toml` dependency changes vs. original plan

**Removed** (no LangGraph or LangChain):
```
# langgraph>=0.2.0         ← removed
# langchain-core>=0.3.0    ← removed
```

**Added/Kept**:
```toml
[project.dependencies]
anthropic = ">=0.49.0"      # Claude Agentic SDK (primary)
openai = ">=1.0.0"          # optional fallback provider
mcp = ">=1.0.0"             # MCP server + client library
fastapi = ">=0.115.0"
uvicorn = {extras=["standard"], version=">=0.30.0"}
pydantic = ">=2.7.0"
pydantic-settings = ">=2.3.0"
sqlalchemy = {extras=["asyncio"], version=">=2.0.0"}
aiosqlite = ">=0.20.0"
pdfplumber = ">=0.11.0"
python-docx = ">=1.1.0"
openpyxl = ">=3.1.0"
pandas = ">=2.2.0"
jinja2 = ">=3.1.0"
python-multipart = ">=0.0.9"
httpx = ">=0.27.0"

[project.optional-dependencies]
dev = ["pytest>=8.0", "pytest-asyncio>=0.23", "pytest-cov>=5.0", "httpx"]
```

---

## 3. Tasks

### Phase 1 — Foundation (~3h)

1. **Project scaffold** (0.5h) — `server/` directory, `pyproject.toml` with all deps (no langgraph/langchain), `.env.example`, `pytest.ini` | Deps: None | Risk: L
2. **FastAPI app factory + health route** (0.5h) — `main.py` with lifespan, `config.py` pydantic-settings, `GET /health` | Deps: Task 1 | Risk: L
3. **Pydantic schemas** (1h) — all schemas in `schemas/` (enums, api, discovery, policies, architecture, estimation, report) | Deps: Task 1 | Risk: L
4. **LLM provider abstraction** (1h) — `LLMClient` protocol, `AnthropicProvider` (primary, uses `claude-opus-4-8`), `OpenAIProvider`, factory. `AnthropicProvider` wraps `anthropic.AsyncAnthropic` | Deps: Task 3 | Risk: M

### Phase 2 — Document Parsing (~2.5h)

5. **ParsedDocument model + parser dispatcher** (0.5h) — normalised output schema, `parse(bytes, content_type)` factory | Deps: Task 3 | Risk: L
6. **PDF extractor** (0.5h) — `pdfplumber`; extract text + table blocks | Deps: Task 5 | Risk: M (scanned PDFs return empty text)
7. **DOCX extractor** (0.5h) — `python-docx`; paragraphs + tables | Deps: Task 5 | Risk: L
8. **Excel/CSV extractor** (0.5h) — `openpyxl` + `pandas`; per-sheet tabular blocks | Deps: Task 5 | Risk: L
9. **Upload handler wired to parser** (0.5h) — `POST /api/assess` partial: receive file, call parser, return `ParsedDocument` | Deps: Tasks 5-8 | Risk: L

### Phase 3 — Policies DB + MCP Server (~4h)

10. **SQLAlchemy ORM models + engine setup** (0.5h) — `persistence/policies_db.py`; all 5 tables | Deps: Task 3 | Risk: L
11. **Seed data** (1h) — realistic policies for AWS, Azure, GCP; ≥3 compliance frameworks; ≥5 past migration patterns per CSP | Deps: Task 10 | Risk: M (data quality determines Policies Agent output quality)
12. **MCP server** (1.5h) — `mcp/server/server.py` using the `mcp` Python library; register 4 tool handlers; `repository.py` with SQLAlchemy queries; expose via STDIO transport | Deps: Tasks 10-11 | Risk: H (mcp library STDIO lifecycle needs careful management)
13. **MCP client wrapper** (1h) — `mcp/client.py`; `MCPClient.list_tools_as_anthropic_format()` (converts MCP tool schemas to Anthropic `Tool` format); `call_tool(name, args)`; retry-with-backoff; in-process STDIO client using `mcp` library | Deps: Task 12 | Risk: M

### Phase 4 — Agent Implementations (~5.5h)

14. **BaseAgent + AssessmentContext** (0.5h) — `context.py` dataclass; `agents/base.py` with `_emit_audit()` helper; `run()` protocol | Deps: Tasks 3, 4 | Risk: L
15. **Discovery Agent** (1h) — builds document prompt; calls `client.messages.parse()` with `output_config.format` JSON schema; returns `AppProfile`; handles partial extraction via Pydantic `model_validate` | Deps: Tasks 3, 4, 14 | Risk: H (LLM structured output reliability)
16. **Org Policies Agent** (1.5h) — manual tool-use agentic loop; calls 4 MCP tools; assembles `PolicyContext` from accumulated tool results; degrades gracefully on partial MCP failure | Deps: Tasks 3, 13, 14 | Risk: M
17. **Architecture Agent** (1.5h) — injects `AppProfile` + `PolicyContext` summary into prompt; validates recommended services are in approved list; returns `ArchitecturePlan` via structured output | Deps: Tasks 3, 4, 14 | Risk: H (prompt engineering; policy constraint injection)
18. **Estimation Agent** (1h) — uses `AppProfile` + `ArchitecturePlan`; parametric effort model in prompt; returns `EstimationReport` via structured output | Deps: Tasks 3, 4, 14 | Risk: M

### Phase 5 — Orchestrator + Async Pipeline (~3h)

19. **CloudMigrationOrchestrator** (1h) — `orchestrator.py`; `async def run(doc, csp)` method; `asyncio.gather(discovery.run(ctx), policies.run(ctx), return_exceptions=True)` for parallel phase; sequential calls for Architecture → Estimation; `compose_report()` | Deps: Tasks 14-18 | Risk: M (exception handling across `gather()` must not drop audit events)
20. **Conflict detection + resolution** (0.5h) — post-gather check: if Architecture strategy contradicts Discovery complexity tier, emit warning audit event + lower confidence | Deps: Task 19 | Risk: M
21. **Audit trail persistence** (0.5h) — `audit/trail.py`; writes `AuditEvent` list from `AssessmentContext` to `audit.sqlite` after pipeline completes | Deps: Tasks 14, 19 | Risk: L
22. **`AssessmentContext` status management** (0.5h) — set `status="partial"` when any agent errored but pipeline continued; `status="failed"` when critical agents failed; surface in `AssessResponse` | Deps: Task 19 | Risk: L
23. **DI wiring in `deps.py`** (0.5h) — `get_orchestrator()` FastAPI dependency; starts MCP server subprocess on lifespan startup; constructs client and orchestrator | Deps: Tasks 12-13, 19 | Risk: L

### Phase 6 — Report Builder + API Integration (~2h)

24. **Report composer** (0.5h) — `compose_report(ctx)` assembles `AssessmentReport` from all context outputs + audit summary | Deps: Tasks 14-21 | Risk: L
25. **JSON + Markdown serialisation** (0.5h) — `AssessmentReport → dict`; Markdown template via Jinja2 | Deps: Task 24 | Risk: L
26. **Complete `POST /api/assess` endpoint** (1h) — wire: upload → parse → orchestrator.run() → report → `AssessResponse`; error responses; CORS headers matching Next.js client origin | Deps: Tasks 9, 19, 24-25 | Risk: L

### Phase 7 — Tests (~3h)

27. **Parser unit tests** (0.5h) — fixture files for each format; assert `ParsedDocument` fields | Deps: Tasks 5-8 | Risk: L
28. **MCP tool unit tests** (0.5h) — seed in-memory SQLite; call each MCP tool handler directly (bypassing STDIO); assert returns | Deps: Tasks 10-12 | Risk: L
29. **Agent unit tests (mocked LLM + MCP)** (1h) — mock `client.messages.parse()` / `messages.create()` to return fixture responses; assert each agent returns correct schema shape | Deps: Tasks 14-18 | Risk: M
30. **Orchestrator integration test** (0.5h) — full pipeline with mocked LLM + in-process MCP; assert `AssessmentContext` has all outputs set and `len(audit_events) >= 8` | Deps: Tasks 19-26 | Risk: M
31. **API integration test** (0.5h) — `httpx.AsyncClient` against FastAPI test app; upload fixture PDF; assert `200` + `assessment_id` in response | Deps: Task 26 | Risk: L

**Total**: ~26h

---

## 4. Quality Strategy

- **Tests**: `pytest` + `pytest-asyncio`; unit tests for parsers, MCP tools, agents (mocked); integration tests for orchestrator and API. Target ≥80% coverage on `agents/`, `mcp/`, `orchestrator.py`.
- **Structured output reliability**: `client.messages.parse()` with `output_config.format` provides Pydantic-validated JSON. Fallback: if `parsed_output` is None (refusal or schema mismatch), return a partial schema with `confidence=0` and emit an audit warning.
- **Partial failure resilience**: `asyncio.gather(return_exceptions=True)` catches agent failures without aborting the pipeline. Architecture Agent receives degraded inputs (None policy context) and still runs with a warning.
- **Audit completeness**: every `messages.create()` call, every MCP tool call, every agent entry/exit emits an `AuditEvent` — verified by the orchestrator integration test asserting `len(audit_events) >= 8` per run.
- **Model choice**: all agents default to `claude-opus-4-8`; `thinking: {type: "adaptive"}` enabled on Discovery and Architecture (complex reasoning tasks); disabled on Estimation (parametric model, structured extraction).

---

## 5. Risks

| Risk | Impact | Mitigation |
|---|---|---|
| LLM structured output unreliable (hallucinated fields, wrong types) | H | `client.messages.parse()` with `output_config.format` + Pydantic validation; fallback to partial extraction; test with fixture documents |
| MCP `mcp` library STDIO lifecycle management | H | Implement MCP repository as direct function calls first (integration test without STDIO); add STDIO transport wrapper after agents pass unit tests |
| Seed data quality determines Architecture Agent output quality | M | Write ≥15 realistic policies per CSP; include approved service lists; review seed before wiring Architecture Agent |
| `asyncio.gather()` exception silently swallowed | M | Always use `return_exceptions=True`; assert result types before assigning to context; log exceptions before degraded-mode continuation |
| pdfplumber returns empty text for scanned/image PDFs | M | Detect empty extraction; return warning in `ParsedDocument.warnings`; surface to user in API response |
| Anthropic/OpenAI structured output APIs differ | M | Abstract inside each provider; `AnthropicProvider` uses `messages.parse()` + `output_config.format`; `OpenAIProvider` uses `response_format={"type":"json_object"}` |

**Assumptions**:
- `anthropic>=0.49.0` supports `messages.parse()` with `output_config.format` for structured outputs.
- The `mcp` Python library supports in-process STDIO transport for the MVP (no network hop needed).
- `claude-opus-4-8` with `thinking: {type: "adaptive"}` is available under the provided API key.
- SQLite is sufficient for the policy store at current data volumes.

**Out of scope** (deferred):
- DOCX / PDF report file generation (Markdown + JSON MVP is sufficient for now)
- WebSocket streaming of agent progress events to frontend
- Multi-tenant / auth layer
- CMDB integrations (ServiceNow, Flexera)
- Cost modelling agent
- Gemini provider (Claude + OpenAI cover MVP)

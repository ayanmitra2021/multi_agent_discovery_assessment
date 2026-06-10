# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Purpose

AI-powered cloud migration assessment assistant. Users upload application portfolio documents (Word, PDF, Excel) and the system returns migration assessments, architecture recommendations, and effort estimates through a conversational web interface.

## Tech Stack

| Layer | Technology |
|---|---|
| Web UI | React + TypeScript + Tailwind CSS |
| Backend API | FastAPI (Python 3.11+) |
| Agent Framework | LangGraph / custom orchestration |
| LLM Providers | Anthropic Claude (default), OpenAI GPT-4o, Google Gemini |
| Document Parsing | `python-docx`, `pdfplumber`, `openpyxl` |
| Report Generation | `python-docx`, `reportlab`, Jinja2 templates |

## Commands

```bash
# Backend
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000

# Frontend (from ui/ directory)
npm install
npm run dev
```

Frontend runs at `http://localhost:5173`, backend at `http://localhost:8000`.

## Environment Setup

Copy `.env.example` to `.env` and configure:

```env
LLM_PROVIDER=claude          # claude | openai | gemini
ANTHROPIC_API_KEY=...
DEFAULT_TARGET_CLOUD=aws     # aws | azure | gcp | multi
ENABLE_MULTI_AGENT=true
ESTIMATION_MODEL=parametric  # parametric | analogous
MAX_APPS_PER_RUN=50
REPORT_FORMAT=docx           # docx | pdf | json | markdown
REPORT_OUTPUT_DIR=./outputs
MAX_UPLOAD_SIZE_MB=25
```

## Agent Architecture

The system uses a multi-agent orchestration pattern. The **Orchestrator Agent** is the sole entry point — it parses intent, builds an execution plan, invokes sub-agents in sequence, resolves conflicts between outputs, and assembles the final report. Sub-agents are not called directly by the user.

```
User → Orchestrator → [Discovery ∥ OrgPolicies] → Architecture → Estimation → Merge → Report
```

**Discovery Agent** — extracts structured facts from uploaded documents: app name/owner, tech stack, dependency map, tech debt indicators, cloud readiness signals.

**Org Policies Agent** — runs in parallel with Discovery. Fetches the organisation's migration standards and mandatory controls: approved services, prohibited configurations, encryption/networking requirements, applicable compliance frameworks (SOC 2, ISO 27001, GDPR, etc.), and landing zone standards. Its output is passed directly to the Architecture Agent so recommendations are policy-compliant before being generated, not reviewed after.

**Architecture Agent** — takes Discovery output **and** Org Policies output and recommends target-state architecture: migration strategy (Rehost/Replatform/Refactor/Replace/Retire), cloud service mapping, landing zone pattern, security controls aligned to org standards.

**Estimation Agent** — takes Discovery + Architecture output and produces effort estimates: story points or day-based sizing by workstream (infra/app/data/testing), wave groupings, risk-adjusted timelines.

The Orchestrator handles partial execution — not all four sub-agents are invoked for every request. When sub-agent outputs conflict (e.g., Discovery says HIGH complexity but Estimation disagrees), the Orchestrator must detect and resolve before generating the report.

## Input / Output Contract

**Accepted inputs:** `.pdf`, `.docx`, `.xlsx`, `.csv`, plain text prompts

**Produced outputs:** Markdown/JSON current-state summary, JSON+HTML complexity assessment (scored across 6 dimensions), Markdown target architecture, Markdown/XLSX roadmap, consolidated DOCX/PDF report

All agent decisions must be logged with rationale for audit trail purposes.

## Key Design Decisions

- **LLM-agnostic**: The backend must support swapping between Claude, GPT-4o, and Gemini via `LLM_PROVIDER` env var — avoid provider-specific SDK idioms bleeding into agent logic.
- **`ENABLE_MULTI_AGENT=false`** collapses the pipeline to single-agent mode — the orchestration layer must gracefully handle this without changing the public API surface.
- **Portfolio limit**: `MAX_APPS_PER_RUN=50` — document parsers and agent loops must respect this cap.
- **Report output**: Written to `REPORT_OUTPUT_DIR`; the web UI offers download after generation.
- **MCP hook chain**: `MCPClient.call_tool()` runs a **pre/post hook chain** around every MCP tool invocation — all 10 hooks defined in `app/mcp/hooks.py`. Pre-hooks (in order): pre-call audit logging, input normalization, CSP validation, argument bounds enforcement, per-session call budget. Post-hooks (in order): error normalization, empty-result enrichment, result size limiting, metadata enrichment, post-call audit logging. This is the single enforcement point for all MCP tool safety — no per-tool or per-agent defensive coding should be added elsewhere. When introducing new MCP tools, the hook chain applies automatically with zero extra work.

## MCP Hook Chain

The hook chain lives entirely in `app/mcp/hooks.py` and is wired into `MCPClient.__init__()`. Key invariants to preserve:

- `CSPGuardHook` must execute **after** `InputNormalizationHook` — normalization lowercases `"AWS"` to `"aws"` before the guard validates it.
- `ErrorNormalizationHook` must be the **first post-hook** — it wraps all subsequent post-hooks' input in a safe state if the underlying tool call threw an exception.
- `SizeLimiterHook` must preserve valid JSON after truncation — it trims the record list, not raw character bytes.
- `CallBudgetHook` keyed on `(tool_name, frozenset(args.items()))` — different args to the same tool are always allowed through; only exact duplicates are short-circuited.
- `call_tool(name, args, ctx)` now requires `AssessmentContext` — do not call it without one. The audit hooks write directly to `ctx.audit_events`.

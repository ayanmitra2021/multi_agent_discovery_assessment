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
User → Orchestrator → [Discovery, Architecture, Estimation] → Merge → Report
```

**Discovery Agent** — extracts structured facts from uploaded documents: app name/owner, tech stack, dependency map, tech debt indicators, cloud readiness signals.

**Architecture Agent** — takes Discovery output and recommends target-state architecture: migration strategy (Rehost/Replatform/Refactor/Replace/Retire), cloud service mapping, landing zone pattern, security considerations.

**Estimation Agent** — takes Discovery + Architecture output and produces effort estimates: story points or day-based sizing by workstream (infra/app/data/testing), wave groupings, risk-adjusted timelines.

The Orchestrator handles partial execution — not all three sub-agents are invoked for every request. When sub-agent outputs conflict (e.g., Discovery says HIGH complexity but Estimation disagrees), the Orchestrator must detect and resolve before generating the report.

## Input / Output Contract

**Accepted inputs:** `.pdf`, `.docx`, `.xlsx`, `.csv`, plain text prompts

**Produced outputs:** Markdown/JSON current-state summary, JSON+HTML complexity assessment (scored across 6 dimensions), Markdown target architecture, Markdown/XLSX roadmap, consolidated DOCX/PDF report

All agent decisions must be logged with rationale for audit trail purposes.

## Key Design Decisions

- **LLM-agnostic**: The backend must support swapping between Claude, GPT-4o, and Gemini via `LLM_PROVIDER` env var — avoid provider-specific SDK idioms bleeding into agent logic.
- **`ENABLE_MULTI_AGENT=false`** collapses the pipeline to single-agent mode — the orchestration layer must gracefully handle this without changing the public API surface.
- **Portfolio limit**: `MAX_APPS_PER_RUN=50` — document parsers and agent loops must respect this cap.
- **Report output**: Written to `REPORT_OUTPUT_DIR`; the web UI offers download after generation.

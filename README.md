# 🚀 AI-Powered Cloud Migration Assessment Assistant

> An agentic AI system that ingests application portfolio documents and produces structured migration assessments, architecture recommendations, and effort estimates — through a conversational web interface.

---

## Table of Contents

- [Overview](#overview)
- [Key Capabilities](#key-capabilities)
- [Agent Architecture](#agent-architecture)
  - [Orchestrator Agent](#orchestrator-agent)
  - [Discovery Agent](#discovery-agent)
  - [Org Policies Agent](#org-policies-agent)
  - [Architecture Agent](#architecture-agent)
  - [Estimation Agent](#estimation-agent)
- [Input Formats](#input-formats)
- [Output Artifacts](#output-artifacts)
- [System Architecture Diagram](#system-architecture-diagram)
- [Getting Started](#getting-started)
- [Configuration](#configuration)
- [Example Workflow](#example-workflow)
- [Tech Stack](#tech-stack)
- [Roadmap](#roadmap)
- [Contributing](#contributing)

---

## Overview

Cloud migration programs routinely stall in their early phases — not from lack of tooling, but from the time it takes to assess applications manually. This system accelerates that first mile.

A user uploads an **application portfolio document** (Word, PDF, or Excel). The AI agent pipeline analyzes it and returns:

- A **current-state architecture summary** for the portfolio or individual application
- A **migration complexity assessment** across dimensions such as dependencies, tech debt, and cloud readiness
- A **target architecture recommendation** (cloud platform, hosting model, landing zone pattern)
- A **migration roadmap** with wave groupings and effort estimates

Interaction happens through a lightweight **web UI** that supports document upload, follow-up questions, and report download.

---

## Key Capabilities

| Capability | Description |
|---|---|
| Multi-format ingestion | Accepts `.docx`, `.pdf`, `.xlsx`, `.csv` portfolio inputs |
| Agentic decomposition | Orchestrator routes tasks to specialized sub-agents |
| LLM-agnostic design | Works with Claude, GPT-4o, or Gemini backends |
| Structured output | Produces JSON, Markdown, and downloadable PPTX/DOCX reports |
| Conversational follow-up | Users can ask clarifying questions after initial assessment |
| Audit trail | Every agent decision is logged with rationale |

---

## Agent Architecture

The system uses a **multi-agent orchestration pattern**: a coordinator agent interprets the user's intent and delegates to specialist sub-agents, each focused on a narrow analytical task.

```
User Upload + Prompt
        │
        ▼
┌─────────────────────┐
│   Orchestrator Agent │  ◄── "Program Manager"
│   (Intent → Plan)   │
└──────────┬──────────┘
           │
     ┌─────┴──────┐
     ▼            ▼
┌────────┐  ┌──────────┐
│Discovery│  │Org Policy│  ← run in parallel
│ Agent   │  │  Agent   │
└────┬───┘  └─────┬────┘
     └──────┬─────┘
            ▼
     ┌──────────────┐
     │ Architecture │
     │    Agent     │
     └──────┬───────┘
            │
            ▼
     ┌──────────────┐
     │  Estimation  │
     │    Agent     │
     └──────┬───────┘
            │
            ▼
  ┌──────────────────────────┐
  │    Orchestrator: Merge   │
  │    + Conflict Resolution │
  └──────────────┬───────────┘
                 ▼
          Final Report
```

---

### Orchestrator Agent

**Role:** Program Manager  
**Trigger:** Any user message or document upload

The Orchestrator is the entry point for all interactions. It parses the user's intent, constructs an execution plan, invokes sub-agents in the appropriate sequence, aggregates their outputs, resolves conflicts between assessments, and assembles the final deliverable.

**Responsibilities:**

- Parse natural language requests and extract task parameters
- Determine which sub-agents to invoke (not all four are always needed)
- Manage execution order and handle sub-agent failures gracefully
- Detect and resolve conflicting outputs (e.g. Discovery flags high complexity; Estimation disagrees)
- Generate the consolidated migration assessment report

**Example invocation:**

```
User: "Assess this VB6 application for migration to AWS and provide an effort estimate."

Orchestrator plan:
  1. Call Discovery Agent    → extract app characteristics        ┐ parallel
  2. Call Org Policies Agent → fetch org migration standards      ┘
  3. Call Architecture Agent → recommend target state on AWS (uses 1 + 2)
  4. Call Estimation Agent   → size the effort (uses 1 + 3)
  5. Merge outputs and generate report
```

---

### Discovery Agent

**Role:** Technical Analyst  
**Input:** Uploaded document (parsed text + metadata)

Extracts structured facts about the application or portfolio from unstructured source material.

**Outputs:**
- Application name, owner, business criticality
- Current technology stack (language, runtime, DB, OS)
- Dependency map (internal and external integrations)
- Identified technical debt indicators
- Cloud readiness signals (containerizability, statelessness, data residency constraints)

---

### Org Policies Agent

**Role:** Policy & Standards Advisor  
**Input:** Target cloud platform + organisation identifier (resolved from session context)

Fetches and normalises the organisation's internal best practices and mandatory policies for cloud migration, ensuring the Architecture Agent's recommendations are compliant before they are generated rather than reviewed after the fact.

**Outputs:**
- Approved cloud services and patterns (e.g. container-first, approved database tiers)
- Prohibited services or configurations (e.g. public S3 buckets, unapproved regions)
- Mandatory controls: encryption at rest/in transit, tagging standards, network topology (hub-spoke, private endpoints)
- Compliance frameworks that apply to the workload (SOC 2, ISO 27001, GDPR, FedRAMP)
- Landing zone and account/subscription structure standards
- Escalation flags for workloads that require a security or compliance review before migration

---

### Architecture Agent

**Role:** Cloud Solutions Architect  
**Input:** Discovery Agent output + Org Policies Agent output + target cloud platform (if specified)

Produces a recommended target-state architecture based on the application profile.

**Outputs:**
- Migration strategy recommendation: Rehost / Replatform / Refactor / Replace / Retire
- Target cloud platform and service mapping (e.g. AWS ECS, Azure App Service, GCP Cloud Run)
- Landing zone pattern recommendation
- Security and compliance considerations
- Architecture decision rationale

---

### Estimation Agent

**Role:** Delivery Estimator  
**Input:** Discovery Agent output + Architecture Agent recommendation

Produces a structured effort estimate and migration roadmap.

**Outputs:**
- Story point or day-based effort estimate by workstream (infra, app, data, testing)
- Wave grouping recommendation (which apps migrate together)
- Risk-adjusted timeline with confidence range
- Assumptions and dependencies log

---

## Input Formats

| Format | Supported Content |
|---|---|
| `.pdf` | Architecture docs, assessment questionnaires, RFPs |
| `.docx` | Application profiles, migration intake forms |
| `.xlsx` / `.csv` | Portfolio registers, CMDB exports, app inventory sheets |
| Plain text prompt | Direct user questions or instructions |

---

## Output Artifacts

| Artifact | Format | Description |
|---|---|---|
| Current-State Summary | Markdown / JSON | Structured app profile extracted by Discovery Agent |
| Complexity Assessment | JSON + HTML table | Scored across 6 dimensions (tech debt, integrations, data, etc.) |
| Target Architecture | Markdown + diagram | Cloud service mapping and migration strategy |
| Roadmap & Effort Estimate | Markdown / XLSX | Wave plan with effort ranges and assumptions |
| Full Assessment Report | DOCX / PDF | Consolidated deliverable for client or stakeholder distribution |

---

## System Architecture Diagram

```
┌──────────────────────────────────────────────────────┐
│                     Web UI (React)                    │
│   [ Upload Document ]   [ Chat Interface ]            │
└───────────────────────┬──────────────────────────────┘
                        │ REST / WebSocket
                        ▼
┌──────────────────────────────────────────────────────┐
│                 API Gateway / Backend                 │
│           (FastAPI / Node.js + Auth layer)            │
└──────┬────────────────┬──────────────────────────────┘
       │                │
       ▼                ▼
┌────────────┐   ┌──────────────────┐
│  Document  │   │  Orchestrator    │
│  Parser    │──►│  Agent (LLM)     │
│ (PDF/DOCX/ │   │                  │
│  XLSX)     │   └──┬──────────┬────┘
└────────────┘      │          │
               ┌────┴───┐  ┌───┴──────┐
               │Disco-  │  │Org Policy│  (parallel)
               │very    │  │  Agent   │
               │Agent   │  │          │
               └───┬────┘  └────┬─────┘
                   └──────┬─────┘
                          ▼
                     ┌──────────┐
                     │  Arch.   │
                     │  Agent   │
                     └────┬─────┘
                          ▼
                     ┌──────────┐
                     │Estimation│
                     │  Agent   │
                     └────┬─────┘
                          │
                          ▼
                ┌──────────────────┐
                │  Report Builder  │
                │ (DOCX/PDF/JSON)  │
                └──────────────────┘
```

---

## Getting Started

### Prerequisites

- Python 3.11+
- Node.js 18+ (for the web UI)
- An API key for your chosen LLM provider (Claude / OpenAI / Gemini)

### Installation

```bash
# Clone the repository
git clone https://github.com/your-org/cloud-migration-assistant.git
cd cloud-migration-assistant

# Install backend dependencies
pip install -r requirements.txt

# Install frontend dependencies
cd ui && npm install && cd ..
```

### Environment Setup

```bash
cp .env.example .env
```

Edit `.env` with your configuration:

```env
LLM_PROVIDER=claude                        # claude | openai | gemini
ANTHROPIC_API_KEY=your_key_here
OPENAI_API_KEY=your_key_here               # optional
GEMINI_API_KEY=your_key_here               # optional

DEFAULT_TARGET_CLOUD=aws                   # aws | azure | gcp | multi
MAX_UPLOAD_SIZE_MB=25
REPORT_OUTPUT_DIR=./outputs
```

### Run Locally

```bash
# Start the backend
uvicorn app.main:app --reload --port 8000

# Start the frontend (separate terminal)
cd ui && npm run dev
```

Open `http://localhost:5173` in your browser.

---

## Configuration

| Parameter | Default | Description |
|---|---|---|
| `LLM_PROVIDER` | `claude` | Primary LLM backend |
| `DEFAULT_TARGET_CLOUD` | `aws` | Default target platform if not specified by user |
| `ENABLE_MULTI_AGENT` | `true` | Use full agent pipeline; set `false` for single-agent mode |
| `ESTIMATION_MODEL` | `parametric` | `parametric` or `analogous` sizing approach |
| `MAX_APPS_PER_RUN` | `50` | Portfolio size limit per single assessment run |
| `REPORT_FORMAT` | `docx` | Default output format: `docx`, `pdf`, `json`, `markdown` |

---

## Example Workflow

**Input document:** Excel portfolio register with 30 applications, including a legacy VB6 system.

**User prompt:**
```
Assess the VB6 application in tab 3 for migration to AWS.
Recommend a target architecture and give me a rough effort estimate.
```

**Agent execution trace:**

```
[Orchestrator]   Intent: single-app deep assessment, target=AWS, VB6 context
[Orchestrator]   Plan: Discovery ∥ OrgPolicies → Architecture → Estimation → Report

[Discovery]      App: "PolicyAdmin v2.1" | Stack: VB6 + SQL Server 2008 |    ┐
                 12 integrations | No containerization signals |               │ parallel
                 Complexity: HIGH                                              │
                                                                               │
[OrgPolicies]    Standard: Container-first for all new workloads               │
                 Required: Encryption at rest (AES-256), TLS 1.2+             │
                 Network: Hub-Spoke topology, no public endpoints              ┘
                 Compliance: SOC 2 Type II | Flag: regulated data → sec review

[Architecture]   Strategy: Refactor (VB6 → .NET 8 on ECS Fargate)
                 DB: SQL Server → Amazon RDS SQL Server (Multi-AZ, encrypted)
                 Integration: MQ Series → Amazon MQ
                 Landing zone: Spoke VPC via Transit Gateway (per org standard)
                 Risk: Data migration complexity, batch job re-engineering

[Estimation]     Effort: 18–24 weeks | Team: 6 FTEs
                 Workstreams: App (45%), Infra (20%), Data (25%), Test (10%)
                 Confidence: Medium | Key assumption: no regulatory re-certification required

[Orchestrator]   Conflicts: None | Merging outputs → generating report
[Report]         Output: PolicyAdmin_Migration_Assessment.docx
```

---

## Tech Stack

| Layer | Technology |
|---|---|
| Web UI | React + TypeScript + Tailwind CSS |
| Backend API | FastAPI (Python) |
| Agent Framework | LangGraph / custom orchestration |
| LLM Providers | Anthropic Claude, OpenAI GPT-4o, Google Gemini |
| Document Parsing | `python-docx`, `pdfplumber`, `openpyxl` |
| Report Generation | `python-docx`, `reportlab`, Jinja2 templates |
| Storage | Local filesystem / S3-compatible object store |
| Auth | API key or OAuth2 (configurable) |

---

## Roadmap

- [ ] Support for CMDB integrations (ServiceNow, Flexera)
- [ ] Wave planning optimizer using constraint-based scheduling
- [ ] Cost modeling agent (FinOps estimates per target architecture)
- [ ] Deloitte Cloud Migration Factory template alignment
- [ ] Multi-tenant SaaS deployment mode
- [ ] Integration with Azure DevOps / Jira for backlog generation

---

## Contributing

Pull requests are welcome. For significant changes, open an issue first to discuss the proposed approach.

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/your-feature`
3. Commit with clear messages following [Conventional Commits](https://www.conventionalcommits.org/)
4. Push and open a pull request against `main`

---

## License

MIT License. See [LICENSE](./LICENSE) for details.
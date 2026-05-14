# AI Consulting Studio

**AI Consulting Studio** is a multi-agent AI management consulting system that turns messy founder/business problem statements into structured, founder-grade decision briefs.

Instead of giving one generic chatbot answer, the system breaks the case into multiple specialized perspectives:

- **Intake Agent** — structures the business problem
- **Finance Agent** — analyzes losses, margins, runway, and capital pressure
- **Operations Agent** — analyzes delivery, execution, process inefficiency, and cost-to-serve
- **Strategy Agent** — analyzes pricing, market positioning, segmentation, and growth quality
- **Reviewer Agent** — resolves tradeoffs and synthesizes the final cross-functional recommendation
- **Founder Report Layer** — produces a concise, decision-oriented final brief for founders/operators

The goal is to simulate how a consulting team would approach a founder’s business problem, but in a faster, more structured, and more explainable way.

---

## Problem

Founders often describe business problems in messy, incomplete language:

- “Revenue is growing but margins are worse”
- “CAC is rising and retention is weak”
- “We don’t know whether the issue is pricing, marketing, onboarding, or operations”
- “We need to become cash-flow positive without killing growth”

Traditional consulting is expensive and slow.  
A normal chatbot is fast, but usually too generic.

**AI Consulting Studio** sits in the middle:

- faster than consulting
- more structured than a generic chatbot
- more explainable through multi-agent decomposition and synthesis

---

## What the System Does

A founder gives a business problem in plain language.

The system then:

1. **Extracts structured business facts**
2. **Determines whether the case is analysis-ready**
3. **Runs specialized multi-agent analysis**
4. **Optionally triggers a reviewer-led clarification round**
5. **Produces a founder-facing decision brief**

The final output includes sections like:

- Executive Summary
- Rough Economics Snapshot
- Most Likely Root Causes (Ranked)
- Biggest Risks
- What to Cut Now
- What to Invest In Now
- What Not to Do
- 30/60/90 Day Action Plan
- Weekly Metrics to Track
- Missing Critical Data

---

## Core Features

### 1. Chat-style intake
The system supports a conversational intake flow where the user can describe the business in natural language.

### 2. Three analysis modes
- **Quick** — fewer follow-up questions, faster analysis
- **Guided** — structured consultant-style questioning
- **Detailed** — more diligence-style intake before analysis

### 3. Structured case extraction
The intake layer converts free-text founder input into a structured business case.

Tracked fields include:

- company_name
- industry
- business_model
- revenue_amount
- revenue_period
- profit_or_loss_amount
- profit_or_loss_type
- gross_margin
- headcount
- marketing_spend
- marketing_spend_period
- cash_reserves
- runway
- main_problem
- main_goal
- extra_context

### 4. Multi-agent consulting pipeline
After intake, the system runs a consulting-style analysis pipeline:

- Intake
- Finance
- Operations
- Strategy
- Reviewer
- Founder Report

### 5. Reviewer-led clarification round
The reviewer can identify disagreements or uncertainty across the specialist agents and ask up to 3 targeted follow-up questions before producing the final synthesis.

This improves:
- prioritization
- tradeoff handling
- realism
- final recommendation quality

### 6. Founder-facing report
The final artifact is not just raw agent output.  
It is a founder-facing decision brief optimized for actionability.

### 7. Frontend dashboard
The project includes a dashboard UI with:

- landing page
- chat workspace
- mode selector
- extracted facts panel
- founder report panel
- optional detailed agent outputs
- agent explainer panel

---

## System Architecture

### High-level flow

Founder Prompt
   ↓
Chat Intake / Structured Extraction
   ↓
Readiness Check
   ↓
Intake Agent
   ↓
Finance + Operations + Strategy
   ↓
Reviewer Pass 1
   ↓
Optional Clarification Round
   ↓
Reviewer Pass 2
   ↓
Founder Report

Repository Structure

AI_Agents_project/
│
├── agents/
│   ├── intake_agent.py
│   ├── finance_agent.py
│   ├── operations_agent.py
│   ├── strategy_agent.py
│   ├── reviewer_agent.py
│   └── final_report_agent.py
│
├── prompts/
│   ├── intake_prompt.md
│   ├── finance_prompt.md
│   ├── operations_prompt.md
│   ├── strategy_prompt.md
│   ├── reviewer_prompt.md
│   └── final_report_prompt.md
│
├── schemas/
│   ├── __init__.py
│   └── agent_output.py
│
├── services/
│   ├── __init__.py
│   ├── openai_client.py
│   └── intake_orchestrator.py
│
├── utils/
│   ├── __init__.py
│   ├── prompt_loader.py
│   ├── consulting_json.py
│   ├── case_intake.py
│   └── input_validation.py
│
├── frontend/
│   ├── src/
│   │   ├── app/
│   │   ├── components/
│   │   └── lib/
│   └── package.json
│
├── api_server.py
├── app.py
├── requirements.txt
├── requirements-web.txt
└── README.md


Tech Stack
Backend
Python
FastAPI
OpenAI Responses API
ThreadPoolExecutor for specialist parallelism
Deterministic validation + orchestration logic
Frontend
Next.js
TypeScript
CSS / component-based UI
Chat-style consulting dashboard
AI / Logic Design
OpenAI gpt-4o-mini
Prompt-based specialist agents
Deterministic readiness and validation logic
Reviewer-led clarification round
Structured report formatting and cleanup
How It Works
1. Intake Layer

The user enters a business problem in plain language.

The intake orchestrator:

extracts structured fields
updates the case draft
checks readiness
asks focused follow-up questions when critical information is missing
2. Specialist Analysis

Once enough information is available:

Finance analyzes liquidity, burn, CAC, margin pressure
Operations analyzes onboarding, process gaps, delivery inefficiency, or cost-to-serve
Strategy analyzes pricing, ICP, retention, segmentation, channel quality, growth quality
3. Reviewer Synthesis

The reviewer compares the specialist outputs and identifies:

conflicts
uncertainties
decision-critical tradeoffs

If needed, the reviewer triggers a single bounded clarification round.

4. Founder Report

The final report converts the internal multi-agent analysis into a concise, founder-friendly decision brief.

Example Use Cases

This system works best for cases like:

“Revenue is growing, but profitability is getting worse”
“CAC is rising and retention is weak”
“We need to become cash-flow positive within 2 quarters”
“We do not know whether the main issue is pricing, onboarding, marketing, or operational inefficiency”
“We need a 30/60/90 day plan, not just generic advice”

<img width="1050" height="567" alt="image" src="https://github.com/user-attachments/assets/e0048529-42b4-42ab-ba01-016d877b3de8" />

<img width="1032" height="582" alt="image" src="https://github.com/user-attachments/assets/22abba2a-d4f3-47b9-9a6b-69724aadd770" />



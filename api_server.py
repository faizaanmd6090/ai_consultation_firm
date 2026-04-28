"""
Backend adapter for chat-style intake + analysis pipeline.

Endpoints:
- POST /api/intake/chat
- POST /api/analyze-case
- GET  /api/agent-info
"""

from __future__ import annotations

from typing import Literal
from uuid import uuid4

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from agents.final_report_agent import run_final_report_agent
from app import run_turnaround_pipeline
from services.openai_client import generate_agent_response
from services.intake_orchestrator import (
    choose_next_follow_up,
    ChatIntent,
    SessionState,
    compute_missing_fields,
    compute_readiness,
    detect_chat_intent,
    empty_case_draft,
    extract_case_fields_from_message,
    merge_case_draft,
    summarize_extracted_facts,
)
from utils.case_intake import case_to_client_narrative, normalize_case
from utils.input_validation import (
    validate_intake_case,
)

load_dotenv()

app = FastAPI(title="AI Consulting API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


class CaseInput(BaseModel):
    company_name: str = ""
    industry: str = ""
    business_model: str = ""
    revenue_amount: str = ""
    revenue_period: str = ""
    profit_or_loss_amount: str = ""
    profit_or_loss_type: str = ""
    gross_margin: str = ""
    headcount: str = ""
    marketing_spend: str = ""
    marketing_spend_period: str = ""
    cash_reserves: str = ""
    runway: str = ""
    main_problem: str = ""
    main_goal: str = ""
    extra_context: str = ""


class AnalyzeCaseRequest(BaseModel):
    mode: Literal["quick", "guided", "detailed"] = Field(default="guided")
    case: CaseInput | None = None
    session_id: str | None = None


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class IntakeChatRequest(BaseModel):
    session_id: str | None = None
    mode: Literal["quick", "guided", "detailed"] = Field(default="guided")
    user_message: str = Field(min_length=1)


class IntakeSession(BaseModel):
    session_id: str
    mode: Literal["quick", "guided", "detailed"]
    messages: list[ChatMessage] = Field(default_factory=list)
    structured_case_draft: CaseInput = Field(default_factory=CaseInput)
    missing_fields: list[str] = Field(default_factory=list)
    readiness_score: int = 0
    can_run_analysis: bool = False
    state: SessionState = "collecting_info"
    detected_intent: ChatIntent = "add_context"
    last_follow_up_question: str = ""
    last_follow_up_field: str = ""


SESSIONS: dict[str, IntakeSession] = {}


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


def _llm_assistant_reply(mode: str, user_message: str, draft: CaseInput, missing: list[str], readiness_score: int, can_run: bool, follow_up: str) -> str:
    draft_json = draft.model_dump_json(indent=2)
    missing_csv = ", ".join(missing) if missing else "none"
    instructions = (
        "You are an AI management consulting intake assistant.\n"
        "Respond in a concise, professional tone.\n"
        "You are in chat-intake mode, not final analysis mode.\n"
        "If user input is vague/invalid, ask for clarification naturally.\n"
        "Always end with one concrete next question unless can_run is true.\n"
        "Keep to 2-5 short lines.\n"
        "Do not include JSON."
    )
    user_input = (
        f"Mode: {mode}\n"
        f"User message: {user_message}\n"
        f"Structured draft:\n{draft_json}\n"
        f"Missing fields: {missing_csv}\n"
        f"Readiness score: {readiness_score}\n"
        f"Can run analysis: {can_run}\n"
        f"Suggested next question: {follow_up}\n"
    )
    try:
        text = generate_agent_response(instructions=instructions, user_input=user_input)
        if text.strip():
            return text.strip()
    except Exception:
        pass
    if can_run:
        return (
            "Great—this looks analysis-ready.\n"
            "I can run the consulting pipeline now, or you can add one more detail before we run."
        )
    return f"Thanks, I captured that.\n{follow_up}"


@app.get("/api/agent-info")
def agent_info() -> dict:
    return {
        "agents": [
            {"id": "intake", "name": "Intake Agent", "description": "Extracts structured business facts and frames the case."},
            {"id": "finance", "name": "Finance Agent", "description": "Assesses cash, profitability, and unit-economics pressure points."},
            {"id": "operations", "name": "Operations Agent", "description": "Identifies execution bottlenecks and delivery-side improvement levers."},
            {"id": "strategy", "name": "Strategy Agent", "description": "Evaluates growth, positioning, pricing, and segment focus options."},
            {"id": "review", "name": "Reviewer Agent", "description": "Synthesizes cross-agent outputs into an integrated priority order."},
            {"id": "founder_report", "name": "Founder Report Layer", "description": "Converts synthesis into an executive-ready decision brief."},
        ],
        "orchestration": [
            "Founder describes company situation in chat.",
            "Intake orchestration updates structured case draft.",
            "System asks targeted follow-up questions for missing critical fields.",
            "Finance, Operations, and Strategy analyze the case.",
            "Reviewer synthesizes outputs and prioritizes actions.",
            "Founder report presents final decision summary and execution plan.",
        ],
    }


@app.post("/api/intake/chat")
def intake_chat(payload: IntakeChatRequest) -> dict:
    session_id = payload.session_id or str(uuid4())
    session = SESSIONS.get(session_id)
    if session is None:
        session = IntakeSession(session_id=session_id, mode=payload.mode)
        session.structured_case_draft = CaseInput(**empty_case_draft())
        SESSIONS[session_id] = session
    else:
        session.mode = payload.mode

    user_message = payload.user_message.strip()
    session.messages.append(ChatMessage(role="user", content=user_message))

    # Explicit state machine + intent handling.
    session.detected_intent = detect_chat_intent(user_message, session.state)
    if session.detected_intent == "confirm_analysis" and session.state == "ready_to_analyze":
        session.state = "analyzing"
        assistant_message = "Understood — starting analysis now."
        session.messages.append(ChatMessage(role="assistant", content=assistant_message))
        return {
            "session_id": session.session_id,
            "assistant_message": assistant_message,
            "messages": [m.model_dump() for m in session.messages],
            "structured_case_draft": session.structured_case_draft.model_dump(),
            "missing_fields": session.missing_fields,
            "readiness_score": session.readiness_score,
            "can_run_analysis": True,
            "state": session.state,
            "detected_intent": session.detected_intent,
            "last_follow_up_question": session.last_follow_up_question,
            "extracted_facts_summary": summarize_extracted_facts(
                session.structured_case_draft.model_dump(), session.missing_fields, session.readiness_score
            ),
            "should_start_analysis": True,
        }

    extraction = extract_case_fields_from_message(
        mode=session.mode,
        messages=[m.model_dump() for m in session.messages],
        current_draft=session.structured_case_draft.model_dump(),
        user_message=user_message,
    )
    merged = merge_case_draft(session.structured_case_draft.model_dump(), extraction)
    session.structured_case_draft = CaseInput(**merged)
    session.missing_fields = compute_missing_fields(session.structured_case_draft.model_dump(), session.mode)
    session.readiness_score, session.can_run_analysis = compute_readiness(session.mode, session.missing_fields)
    session.state = "ready_to_analyze" if session.can_run_analysis else "collecting_info"

    follow_up, follow_up_field = choose_next_follow_up(
        session.mode,
        session.structured_case_draft.model_dump(),
        session.missing_fields,
        last_follow_up_field=session.last_follow_up_field or None,
    )
    session.last_follow_up_field = follow_up_field
    session.last_follow_up_question = follow_up
    assistant_message = _llm_assistant_reply(
        mode=session.mode,
        user_message=user_message,
        draft=session.structured_case_draft,
        missing=session.missing_fields,
        readiness_score=session.readiness_score,
        can_run=session.can_run_analysis,
        follow_up=follow_up,
    )
    session.messages.append(ChatMessage(role="assistant", content=assistant_message))

    return {
        "session_id": session.session_id,
        "assistant_message": assistant_message,
        "messages": [m.model_dump() for m in session.messages],
        "structured_case_draft": session.structured_case_draft.model_dump(),
        "missing_fields": session.missing_fields,
        "readiness_score": session.readiness_score,
        "can_run_analysis": session.can_run_analysis,
        "state": session.state,
        "detected_intent": session.detected_intent,
        "last_follow_up_question": session.last_follow_up_question,
        "extracted_facts_summary": summarize_extracted_facts(
            session.structured_case_draft.model_dump(), session.missing_fields, session.readiness_score
        ),
        "should_start_analysis": False,
    }


@app.post("/api/analyze-case")
def analyze_case(payload: AnalyzeCaseRequest) -> dict:
    if payload.case is None and not payload.session_id:
        raise HTTPException(status_code=400, detail={"message": "Provide session_id or case payload."})

    if payload.case is not None:
        draft = payload.case.model_dump()
    else:
        session = SESSIONS.get(payload.session_id or "")
        if session is None:
            raise HTTPException(status_code=404, detail={"message": "Session not found."})
        draft = session.structured_case_draft.model_dump()
        payload.mode = session.mode  # type: ignore[assignment]
        session.state = "analyzing"

    normalized = normalize_case(draft)
    ok, errors = validate_intake_case(normalized, payload.mode)
    if not ok:
        raise HTTPException(status_code=400, detail={"message": "Validation failed", "errors": errors})

    client_problem = case_to_client_narrative(normalized)
    agents = run_turnaround_pipeline(client_problem)
    founder_report = run_final_report_agent(
        agents["intake"],
        agents["finance"],
        agents["operations"],
        agents["strategy"],
        agents["review"],
    )
    if payload.session_id and payload.session_id in SESSIONS:
        SESSIONS[payload.session_id].state = "report_ready"
    return {"founder_report": founder_report, "agents": agents}

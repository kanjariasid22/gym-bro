"""LangGraph-shaped orchestrator: hard session state beats intent."""

from __future__ import annotations

from typing import Any, TypedDict

from langgraph.graph import END, StateGraph
from sqlalchemy.orm import Session

from app.agents.guide import run_guide
from app.agents.trainer import run_trainer
from app.domain import chat as chat_domain
from app.domain import sessions as session_domain
from app.llm import chat, chat_json
from app.memory import (
    add_memory,
    get_memory_context,
    planning_session_id,
    workout_session_id,
)
from app.models import AgentMode, ChatRole, User


class GraphState(TypedDict, total=False):
    user_id: int
    message: str
    mode: str
    active_session_id: int | None
    intent: str
    assistant_reply: str
    ui_hints: dict[str, Any]
    tool_results: list[dict[str, Any]]
    memory_context: str
    handoff_summary: str | None
    trigger_handoff: bool


def _classify_intent(message: str, workout_active: bool) -> str:
    try:
        data = chat_json(
            [
                {
                    "role": "system",
                    "content": (
                        "Classify the user message for a training companion. "
                        'Labels: plan|log|meta|start_workout|end_workout|cancel_workout. '
                        'Return JSON {"intent":"..."}.'
                    ),
                },
                {
                    "role": "user",
                    "content": f"workout_active={workout_active}\nmessage={message}",
                },
            ]
        )
        intent = str(data.get("intent") or "meta").strip().lower()
        allowed = {"plan", "log", "meta", "start_workout", "end_workout", "cancel_workout"}
        return intent if intent in allowed else "meta"
    except Exception:
        return "log" if workout_active else "plan"


def build_ui_hints(db: Session, user: User) -> dict[str, Any]:
    active = session_domain.get_active_session(db, user.id)
    mode = "trainer" if active else "guide"
    sets_preview = []
    if active:
        detail = session_domain.get_session_detail(db, user.id, active.id)
        sets_preview = [
            {
                "id": s.id,
                "canonical_name": s.canonical_name,
                "set_index": s.set_index,
                "weight": s.weight,
                "unit": s.unit.value,
                "reps": s.reps,
            }
            for s in detail.set_logs
        ]
    return {
        "mode": mode,
        "active_session": (
            {
                "id": active.id,
                "status": active.status.value,
                "started_at": active.started_at.isoformat() if active.started_at else None,
            }
            if active
            else None
        ),
        "sets": sets_preview,
    }


def run_chat_turn(
    db: Session,
    user: User,
    message: str,
    *,
    handoff_summary: str | None = None,
) -> dict[str, Any]:
    """Execute one user chat turn (or a synthetic Guide turn after handoff)."""
    active = session_domain.get_active_session(db, user.id)
    workout_active = active is not None
    intent = _classify_intent(message, workout_active) if not handoff_summary else "meta"

    # Hard state beats intent
    if workout_active:
        mode = "trainer"
        agent_id = "trainer"
        mem_session = workout_session_id(active.id)
    elif intent in {"log", "start_workout"} and not handoff_summary:
        mode = "trainer"
        agent_id = "trainer"
        mem_session = planning_session_id(user.id)
    else:
        mode = "guide"
        agent_id = "guide"
        mem_session = planning_session_id(user.id)

    owner = str(user.id)
    if not handoff_summary:
        chat_domain.add_message(db, user.id, ChatRole.user, message, mode=None)

    ctx = get_memory_context(
        [{"role": "user", "content": message}],
        owner_id=owner,
        agent_id=agent_id,
        session_id=mem_session,
    )
    memory_context = str(ctx.get("context_string") or "")

    if mode == "trainer":
        result = run_trainer(
            db,
            user,
            message,
            memory_context=memory_context,
            active_session_id=active.id if active else None,
        )
        reply_mode = AgentMode.trainer
    else:
        result = run_guide(
            db,
            user,
            message,
            memory_context=memory_context,
            handoff_summary=handoff_summary,
        )
        reply_mode = AgentMode.guide

    reply = result["reply"]
    chat_domain.add_message(db, user.id, ChatRole.assistant, reply, mode=reply_mode)

    mem_msgs: list[dict[str, str]] = []
    if not handoff_summary:
        mem_msgs.append({"role": "user", "content": message})
    mem_msgs.append({"role": "assistant", "content": reply})
    active_after = session_domain.get_active_session(db, user.id)
    if reply_mode == AgentMode.trainer and active_after:
        write_session = workout_session_id(active_after.id)
        write_agent = "trainer"
    else:
        write_session = planning_session_id(user.id)
        write_agent = "guide"
    add_memory(mem_msgs, owner_id=owner, agent_id=write_agent, session_id=write_session)

    # After Trainer completes via tool → separate Guide handoff turn
    handoff_extra = None
    for tr in result.get("tool_results") or []:
        if tr.get("name") == "complete_workout" and (tr.get("result") or {}).get("needs_handoff"):
            sid = (tr.get("result") or {}).get("session_id")
            if sid:
                handoff_extra = run_handoff_after_complete(db, user, int(sid))
            break

    hints = build_ui_hints(db, user)
    if handoff_extra and handoff_extra.get("ui_hints"):
        hints = handoff_extra["ui_hints"]

    out: dict[str, Any] = {
        "reply": reply,
        "mode": hints.get("mode", reply_mode.value),
        "intent": intent,
        "tool_results": result.get("tool_results") or [],
        "ui_hints": hints,
    }
    if handoff_extra:
        out["handoff_summary"] = handoff_extra.get("handoff_summary")
        if handoff_extra.get("reply"):
            out["reply"] = f"{reply}\n\n{handoff_extra['reply']}"
    return out


def run_handoff_after_complete(db: Session, user: User, session_id: int) -> dict[str, Any]:
    """Complete path: summarize sets → trainer memory → Guide follow-up."""
    detail = session_domain.get_session_detail(db, user.id, session_id)
    lines = [
        f"- {s.canonical_name} set {s.set_index}: {s.weight}{s.unit.value} x {s.reps}"
        + (f" ({s.notes})" if s.notes else "")
        for s in detail.set_logs
    ]
    sets_blob = "\n".join(lines) if lines else "(no sets logged)"
    summary = chat(
        [
            {
                "role": "system",
                "content": (
                    "Summarize this completed workout for the planning Guide. "
                    "Note volume, sticking points, and suggested next focus. Be concise."
                ),
            },
            {"role": "user", "content": sets_blob},
        ],
        temperature=0.3,
        max_tokens=500,
    )
    # Persist summary on session if empty
    if not detail.summary:
        detail.summary = summary
        db.commit()

    owner = str(user.id)
    add_memory(
        [
            {"role": "assistant", "content": f"Workout #{session_id} summary:\n{summary}"},
        ],
        owner_id=owner,
        agent_id="trainer",
        session_id=workout_session_id(session_id),
    )
    # Also give Guide a durable fact-ish note
    add_memory(
        [
            {
                "role": "user",
                "content": f"Handoff from completed workout #{session_id}:\n{summary}",
            }
        ],
        owner_id=owner,
        agent_id="guide",
        session_id=planning_session_id(user.id),
    )

    follow = run_chat_turn(
        db,
        user,
        "I just finished my workout. Based on the handoff summary, what should I focus on next?",
        handoff_summary=summary,
    )
    follow["handoff_summary"] = summary
    return follow


def compile_graph():
    """Optional LangGraph compile for introspection / future expansion."""

    def route_node(state: GraphState) -> GraphState:
        return state

    g = StateGraph(GraphState)
    g.add_node("route", route_node)
    g.set_entry_point("route")
    g.add_edge("route", END)
    return g.compile()

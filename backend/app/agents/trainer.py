"""Trainer agent node — live logging + light same-day swap."""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy.orm import Session

from app.agents.tools import TOOL_SPECS, dispatch_tool, tool_get_today_plan
from app.llm import chat, chat_json
from app.models import User

TRAINER_TOOLS = {
    "start_workout",
    "complete_workout",
    "cancel_workout",
    "log_sets",
    "get_today_plan",
    "swap_exercise_today",
}


def run_trainer(
    db: Session,
    user: User,
    message: str,
    *,
    memory_context: str,
    active_session_id: int | None,
) -> dict[str, Any]:
    plan = tool_get_today_plan(db, user)
    tool_docs = [t for t in TOOL_SPECS if t["name"] in TRAINER_TOOLS]
    system = (
        "You are GymBro Trainer. The user has (or is starting) a live workout. "
        "When the user reports lifts (exercise + weight + reps), ALWAYS call log_sets — "
        "even if the exercise is not on today's plan (log first, then optionally offer swap). "
        "Allow light same-day exercise swaps via swap_exercise_today. "
        "Do NOT replan the whole program. Prefer tools over guessing.\n"
        f"Active session id: {active_session_id}\n"
        f"Today plan: {json.dumps(plan)}\n"
        f"Memory context:\n{memory_context or '(none)'}\n"
        f"Available tools: {json.dumps(tool_docs)}\n"
        "Respond with JSON only: "
        '{"tools":[{"name":"...","args":{...}}],"reply":"final user-facing reply"}. '
        "You may call 0+ tools. Put the conversational reply in reply."
    )
    decision = chat_json(
        [
            {"role": "system", "content": system},
            {"role": "user", "content": message},
        ]
    )
    tool_results: list[dict[str, Any]] = []
    for call in decision.get("tools") or []:
        name = str(call.get("name") or "")
        if name not in TRAINER_TOOLS:
            tool_results.append({"name": name, "result": {"ok": False, "error": "not allowed"}})
            continue
        args = call.get("args") or {}
        result = dispatch_tool(db, user, name, args if isinstance(args, dict) else {})
        tool_results.append({"name": name, "result": result})

    reply = str(decision.get("reply") or "").strip()
    if not reply:
        # Fallback: ask model for a short reply given tool results
        reply = chat(
            [
                {
                    "role": "system",
                    "content": "You are GymBro Trainer. Give a short helpful reply.",
                },
                {
                    "role": "user",
                    "content": f"User said: {message}\nTool results: {json.dumps(tool_results)}",
                },
            ],
            temperature=0.3,
            max_tokens=400,
        )
    return {"reply": reply, "tool_results": tool_results, "mode": "trainer"}

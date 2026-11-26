"""Guide agent node — intake, planning, paste plan, post-handoff."""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy.orm import Session

from app.agents.tools import TOOL_SPECS, dispatch_tool, tool_get_today_plan
from app.llm import chat, chat_json
from app.models import User

GUIDE_TOOLS = {"get_today_plan", "upsert_program", "start_workout"}


def run_guide(
    db: Session,
    user: User,
    message: str,
    *,
    memory_context: str,
    handoff_summary: str | None = None,
) -> dict[str, Any]:
    plan = tool_get_today_plan(db, user)
    tool_docs = [t for t in TOOL_SPECS if t["name"] in GUIDE_TOOLS]
    handoff_block = (
        f"\nPost-workout handoff summary from Trainer:\n{handoff_summary}\n"
        if handoff_summary
        else ""
    )
    system = (
        "You are GymBro Guide. Help the user plan training. "
        "Before creating a new plan, obtain goals AND a plan end date (ask if missing), "
        "OR accept a pasted/typed existing plan and structure it via upsert_program. "
        "Do not log sets. You may suggest starting a workout via start_workout if they are ready.\n"
        f"Current program snapshot: {json.dumps(plan)}\n"
        f"Memory context:\n{memory_context or '(none)'}\n"
        f"{handoff_block}"
        f"Available tools: {json.dumps(tool_docs)}\n"
        "Respond with JSON only: "
        '{"tools":[{"name":"...","args":{...}}],"reply":"final user-facing reply"}.'
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
        if name not in GUIDE_TOOLS:
            tool_results.append({"name": name, "result": {"ok": False, "error": "not allowed"}})
            continue
        args = call.get("args") or {}
        result = dispatch_tool(db, user, name, args if isinstance(args, dict) else {})
        tool_results.append({"name": name, "result": result})

    reply = str(decision.get("reply") or "").strip()
    if not reply:
        reply = chat(
            [
                {
                    "role": "system",
                    "content": "You are GymBro Guide. Give a short helpful planning reply.",
                },
                {
                    "role": "user",
                    "content": f"User said: {message}\nTool results: {json.dumps(tool_results)}",
                },
            ],
            temperature=0.4,
            max_tokens=600,
        )
    return {"reply": reply, "tool_results": tool_results, "mode": "guide"}

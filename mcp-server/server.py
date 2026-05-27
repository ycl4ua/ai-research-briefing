from __future__ import annotations

import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "pipeline"))

import ai_briefing  # noqa: E402


TOOLS = [
    {
        "name": "generate_daily_digest",
        "description": "Fetch configured AI sources, rank items, and write the daily digest.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "offline": {"type": "boolean", "description": "Use sample data instead of network sources."}
            },
        },
    },
    {
        "name": "read_daily_digest",
        "description": "Read the latest generated Top 10 + More 20 digest.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "record_feedback",
        "description": "Record lightweight feedback for one item. Browser feedback is still local in v0.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "item_id": {"type": "string"},
                "feedback": {"type": "string", "enum": ["saved", "read", "hidden", "too_noisy"]},
            },
            "required": ["item_id", "feedback"],
        },
    },
]


def content(payload) -> dict:
    return {"content": [{"type": "text", "text": json.dumps(payload, ensure_ascii=False, indent=2)}]}


def handle(method: str, params: dict | None) -> dict:
    params = params or {}
    if method == "initialize":
        return {
            "protocolVersion": "2024-11-05",
            "capabilities": {"tools": {}},
            "serverInfo": {"name": "ai-research-briefing", "version": "0.1.0"},
        }
    if method == "tools/list":
        return {"tools": TOOLS}
    if method == "tools/call":
        name = params.get("name")
        args = params.get("arguments") or {}
        if name == "generate_daily_digest":
            digest = ai_briefing.build_digest(include_network=not args.get("offline", False))
            ai_briefing.write_json(ai_briefing.DATA / "digests" / "daily.json", digest)
            return content({"status": "ok", "top": len(digest["top_10"]), "more": len(digest["more_20"])})
        if name == "read_daily_digest":
            return content(ai_briefing.read_json(ai_briefing.DATA / "digests" / "daily.json"))
        if name == "record_feedback":
            path = ai_briefing.DATA / "feedback.json"
            feedback = ai_briefing.read_json(path) if path.exists() else []
            feedback.append(args)
            ai_briefing.write_json(path, feedback)
            return content({"status": "ok", "recorded": args})
        raise ValueError(f"Unknown tool: {name}")
    return {}


def respond(message: dict, result=None, error=None) -> None:
    payload = {"jsonrpc": "2.0", "id": message.get("id")}
    if error:
        payload["error"] = {"code": -32000, "message": str(error)}
    else:
        payload["result"] = result
    sys.stdout.write(json.dumps(payload, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def main() -> int:
    for line in sys.stdin:
        if not line.strip():
            continue
        try:
            message = json.loads(line)
            result = handle(message.get("method", ""), message.get("params"))
            if "id" in message:
                respond(message, result=result)
        except Exception as exc:
            respond(message if "message" in locals() else {"id": None}, error=exc)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


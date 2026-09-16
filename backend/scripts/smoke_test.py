#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys

import httpx


QUESTION = "What are the four core functions of the AI RMF?"


def main() -> int:
    parser = argparse.ArgumentParser(description="One-question local backend smoke test")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    args = parser.parse_args()
    checks: list[tuple[str, bool]] = []
    try:
        with httpx.Client(base_url=args.base_url, timeout=600) as client:
            health = client.get("/health")
            checks.append(("health", health.status_code == 200 and health.json().get("status") == "healthy"))
            query = client.post("/query", json={"question": QUESTION, "thinking_enabled": False})
            payload = query.json() if query.headers.get("content-type", "").startswith("application/json") else {}
            conversation_id = payload.get("conversation_id")
            checks.extend([
                ("query", query.status_code == 200),
                ("answer", bool(payload.get("answer"))),
                ("four_sources", len(payload.get("sources", [])) == 4),
                ("thinking_empty", payload.get("thinking") == ""),
            ])
            if conversation_id:
                conversation = client.get(f"/conversations/{conversation_id}")
                roles = [message.get("role") for message in conversation.json().get("messages", [])]
                checks.append(("conversation", conversation.status_code == 200 and roles == ["user", "assistant"]))
                checks.append(("delete", client.delete(f"/conversations/{conversation_id}").status_code == 204))
            else:
                checks.extend([("conversation", False), ("delete", False)])
    except Exception as exc:
        print(f"FAIL connection: {type(exc).__name__}: {exc}")
        return 1
    print(" ".join(f"{name}={'PASS' if passed else 'FAIL'}" for name, passed in checks))
    passed = all(result for _, result in checks)
    print(f"OVERALL={'PASS' if passed else 'FAIL'}")
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())

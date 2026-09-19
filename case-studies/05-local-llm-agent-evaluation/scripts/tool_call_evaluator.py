#!/usr/bin/env python3
"""Bounded evaluator for an OpenAI-compatible tool-calling endpoint.

Saves every raw request/response locally and scores parsed OpenAI tool_calls.
No generated tool calls are executed; mock tool results are injected where needed.
The endpoint defaults to localhost; pass --base-url and --model explicitly as needed.
"""
from __future__ import annotations

import argparse
import json
import re
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable


BASE_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "lookup_ticket",
            "description": "Look up a support ticket by exact ticket id.",
            "parameters": {
                "type": "object",
                "properties": {"ticket_id": {"type": "string"}},
                "required": ["ticket_id"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_docs",
            "description": "Search public documentation by query string.",
            "parameters": {
                "type": "object",
                "properties": {"query": {"type": "string"}},
                "required": ["query"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_current_weather",
            "description": "Get current weather for a city.",
            "parameters": {
                "type": "object",
                "properties": {"location": {"type": "string"}, "unit": {"type": "string"}},
                "required": ["location", "unit"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "lookup_customer",
            "description": "Look up a customer account by email address.",
            "parameters": {
                "type": "object",
                "properties": {"email": {"type": "string"}},
                "required": ["email"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_account_balance",
            "description": "Get the account balance for an exact account id.",
            "parameters": {
                "type": "object",
                "properties": {"account_id": {"type": "string"}},
                "required": ["account_id"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_incident",
            "description": "Create an incident with exact id, numeric severity and notify flag.",
            "parameters": {
                "type": "object",
                "properties": {
                    "incident_id": {"type": "string"},
                    "severity": {"type": "integer"},
                    "notify": {"type": "boolean"},
                },
                "required": ["incident_id", "severity", "notify"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "fetch_record",
            "description": "Fetch an internal record by exact record id.",
            "parameters": {
                "type": "object",
                "properties": {"record_id": {"type": "string"}},
                "required": ["record_id"],
                "additionalProperties": False,
            },
        },
    },
]

REQUEST_PARAMS = {
    "tool_choice": "auto",
    "parallel_tool_calls": False,
    "temperature": 0.6,
    "top_p": 0.95,
    "top_k": 20,
    "repeat_penalty": 1.05,
    "max_tokens": 1024,
    "stream": False,
}


@dataclass
class TrialContext:
    evaluator: "Evaluator"
    scenario_id: str
    attempt: int
    seed: int


class Evaluator:
    def __init__(
        self,
        base_url: str,
        model: str,
        out_dir: Path,
        attempts: int = 5,
        timeout: int = 180,
        capture_server_metadata: bool = False,
    ):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.out_dir = out_dir
        self.raw_dir = out_dir / "raw"
        self.attempts = attempts
        self.timeout = timeout
        self.capture_server_metadata = capture_server_metadata
        self.raw_dir.mkdir(parents=True, exist_ok=True)
        self.results: list[dict[str, Any]] = []

    def get_json(self, path: str) -> Any:
        req = urllib.request.Request(self.base_url + path, headers={"Accept": "application/json", "User-Agent": "local-tool-eval"})
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read().decode("utf-8", "replace"))

    def save_baseline(self) -> dict[str, Any]:
        baseline: dict[str, Any] = {
            "created_at": datetime.now(timezone.utc).isoformat(),
            "base_url": self.base_url,
            "model": self.model,
            "request_params": REQUEST_PARAMS,
            "tool_use_enforcement": "N/A for direct API trials; recorded separately for Hermes runs",
        }
        if self.capture_server_metadata:
            for path in ("/v1/models", "/props", "/slots"):
                try:
                    baseline[path] = self.get_json(path)
                except Exception as exc:
                    baseline[path] = {"error": type(exc).__name__, "message": str(exc)}
        else:
            baseline["server_metadata"] = "not captured; use --capture-server-metadata if local paths and launch details are safe to save"
        (self.out_dir / "baseline.json").write_text(json.dumps(baseline, indent=2, ensure_ascii=False), encoding="utf-8")
        return baseline

    def post_chat(self, ctx: TrialContext, phase: str, messages: list[dict[str, Any]], tools: list[dict[str, Any]] | None, extra: dict[str, Any] | None = None) -> dict[str, Any]:
        payload: dict[str, Any] = {"model": self.model, "messages": messages, **REQUEST_PARAMS, "seed": ctx.seed}
        if tools is not None:
            payload["tools"] = tools
        if extra:
            payload.update(extra)
        safe_name = f"{ctx.scenario_id}_attempt-{ctx.attempt:02d}_{phase}"
        req_path = self.raw_dir / f"{safe_name}_request.json"
        resp_path = self.raw_dir / f"{safe_name}_response.json"
        req_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

        req = urllib.request.Request(
            self.base_url + "/v1/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json", "Authorization": "Bearer no-key"},
            method="POST",
        )
        started = time.time()
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as r:
                raw = r.read().decode("utf-8", "replace")
                elapsed = time.time() - started
                data = json.loads(raw)
                saved = {"http_status": r.status, "elapsed_s": elapsed, "json": data}
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", "replace")
            saved = {"http_status": exc.code, "elapsed_s": time.time() - started, "error_body": body}
        except Exception as exc:
            saved = {"transport_error": type(exc).__name__, "message": str(exc), "elapsed_s": time.time() - started}
        resp_path.write_text(json.dumps(saved, indent=2, ensure_ascii=False), encoding="utf-8")
        return {"request_path": str(req_path), "response_path": str(resp_path), **saved}


def choice(resp: dict[str, Any]) -> dict[str, Any]:
    return (((resp.get("json") or {}).get("choices") or [{}])[0]) if isinstance(resp.get("json"), dict) else {}


def message(resp: dict[str, Any]) -> dict[str, Any]:
    ch = choice(resp)
    return ch.get("message") or {}


def finish_reason(resp: dict[str, Any]) -> str | None:
    return choice(resp).get("finish_reason")


def parse_args(call: dict[str, Any]) -> tuple[dict[str, Any] | None, str | None]:
    raw = (call.get("function") or {}).get("arguments")
    if isinstance(raw, dict):
        return raw, None
    if isinstance(raw, str):
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError as exc:
            return None, f"arguments_not_json: {exc}"
        if not isinstance(parsed, dict):
            return None, f"arguments_not_object: {type(parsed).__name__}"
        return parsed, None
    return None, f"arguments_unexpected_type: {type(raw).__name__}"


def json_equal_strict(actual: Any, expected: Any) -> bool:
    """Compare JSON values without Python's bool/int equality shortcut."""
    if type(actual) is not type(expected):
        return False
    if isinstance(expected, dict):
        return actual.keys() == expected.keys() and all(
            json_equal_strict(actual[key], value) for key, value in expected.items()
        )
    if isinstance(expected, list):
        return len(actual) == len(expected) and all(
            json_equal_strict(a, e) for a, e in zip(actual, expected)
        )
    return actual == expected


def classify_tool_call(resp: dict[str, Any], expected_name: str, expected_args: dict[str, Any]) -> dict[str, Any]:
    if "transport_error" in resp or "error_body" in resp:
        return {"ok": False, "error_class": "transport_failure", "detail": resp.get("message") or resp.get("error_body", "")[:500], "finish_reason": finish_reason(resp)}
    msg = message(resp)
    calls = msg.get("tool_calls") or []
    if not calls:
        return {"ok": False, "error_class": "tool_format_error", "detail": "no parsed message.tool_calls", "finish_reason": finish_reason(resp), "content_prefix": (msg.get("content") or "")[:500]}
    if len(calls) != 1:
        return {"ok": False, "error_class": "wrong_action", "detail": f"expected exactly 1 tool call, got {len(calls)}", "finish_reason": finish_reason(resp), "tool_calls": calls}
    call = calls[0]
    name = (call.get("function") or {}).get("name")
    if name != expected_name:
        return {"ok": False, "error_class": "wrong_action", "detail": f"expected tool {expected_name}, got {name}", "finish_reason": finish_reason(resp), "tool_calls": calls}
    args, err = parse_args(call)
    if err:
        return {"ok": False, "error_class": "tool_format_error", "detail": err, "finish_reason": finish_reason(resp), "tool_calls": calls}
    if not json_equal_strict(args, expected_args):
        return {"ok": False, "error_class": "wrong_arguments", "detail": f"expected parsed args {expected_args!r}, got {args!r}", "finish_reason": finish_reason(resp), "tool_calls": calls, "parsed_arguments": args}
    if finish_reason(resp) != "tool_calls":
        return {"ok": False, "error_class": "tool_format_error", "detail": f"tool call parsed but finish_reason={finish_reason(resp)!r}", "finish_reason": finish_reason(resp), "tool_calls": calls, "parsed_arguments": args}
    return {"ok": True, "error_class": None, "detail": "parsed tool call matched", "finish_reason": finish_reason(resp), "tool_calls": calls, "parsed_arguments": args}


def no_tool_answer(resp: dict[str, Any], predicate: Callable[[str], bool], description: str) -> dict[str, Any]:
    if "transport_error" in resp or "error_body" in resp:
        return {"ok": False, "error_class": "transport_failure", "detail": resp.get("message") or resp.get("error_body", "")[:500], "finish_reason": finish_reason(resp)}
    msg = message(resp)
    calls = msg.get("tool_calls") or []
    content = msg.get("content") or ""
    if calls:
        return {"ok": False, "error_class": "wrong_action", "detail": f"expected no tool call, got {len(calls)}", "finish_reason": finish_reason(resp), "tool_calls": calls, "content_prefix": content[:500]}
    if finish_reason(resp) != "stop":
        return {"ok": False, "error_class": "tool_format_error", "detail": f"expected finish_reason='stop', got {finish_reason(resp)!r}", "finish_reason": finish_reason(resp), "content_prefix": content[:500]}
    if not predicate(content):
        return {"ok": False, "error_class": "wrong_answer", "detail": description, "finish_reason": finish_reason(resp), "content_prefix": content[:500]}
    return {"ok": True, "error_class": None, "detail": "answer matched and no tool call", "finish_reason": finish_reason(resp), "content_prefix": content[:500]}


def assistant_tool_message_from(resp: dict[str, Any]) -> dict[str, Any]:
    msg = message(resp)
    return {"role": "assistant", "content": msg.get("content") or "", "tool_calls": msg.get("tool_calls") or []}


def first_call_id(resp: dict[str, Any]) -> str:
    calls = message(resp).get("tool_calls") or []
    if calls and calls[0].get("id"):
        return calls[0]["id"]
    return "call_missing_id"


def scenario_1(ctx: TrialContext) -> dict[str, Any]:
    resp = ctx.evaluator.post_chat(ctx, "single", [{"role": "user", "content": "Ticket TICKET-481 is failing login after reset. Use the appropriate tool to look up that support ticket. Do not answer in prose."}], BASE_TOOLS)
    score = classify_tool_call(resp, "lookup_ticket", {"ticket_id": "TICKET-481"})
    return {"phases": [{"name": "single", "response_path": resp["response_path"], "request_path": resp["request_path"], "score": score}], "ok": score["ok"], "error_class": score["error_class"]}


def scenario_2(ctx: TrialContext) -> dict[str, Any]:
    expected = {"incident_id": "INC-2026-09-08/α-007", "severity": 2, "notify": False}
    resp = ctx.evaluator.post_chat(ctx, "single", [{"role": "user", "content": "Create incident exactly INC-2026-09-08/α-007 with severity 2 as a number and notify false as a boolean. Use the correct tool only."}], BASE_TOOLS)
    score = classify_tool_call(resp, "create_incident", expected)
    return {"phases": [{"name": "single", "response_path": resp["response_path"], "request_path": resp["request_path"], "score": score}], "ok": score["ok"], "error_class": score["error_class"]}


def scenario_3(ctx: TrialContext) -> dict[str, Any]:
    messages1 = [{"role": "user", "content": "Find the customer account for priya.narayanan+audit@example.co.uk, then use the returned account_id to get the account balance. Start by calling the first required tool."}]
    resp1 = ctx.evaluator.post_chat(ctx, "phase1_find_customer", messages1, BASE_TOOLS)
    score1 = classify_tool_call(resp1, "lookup_customer", {"email": "priya.narayanan+audit@example.co.uk"})
    phases = [{"name": "phase1_find_customer", "response_path": resp1["response_path"], "request_path": resp1["request_path"], "score": score1}]
    if not score1["ok"]:
        return {"phases": phases, "ok": False, "error_class": score1["error_class"]}
    messages2 = [
        messages1[0],
        assistant_tool_message_from(resp1),
        {"role": "tool", "tool_call_id": first_call_id(resp1), "content": json.dumps({"email": "priya.narayanan+audit@example.co.uk", "account_id": "acct_7Z9"})},
    ]
    resp2 = ctx.evaluator.post_chat(ctx, "phase2_get_balance", messages2, BASE_TOOLS)
    score2 = classify_tool_call(resp2, "get_account_balance", {"account_id": "acct_7Z9"})
    phases.append({"name": "phase2_get_balance", "response_path": resp2["response_path"], "request_path": resp2["request_path"], "score": score2})
    return {"phases": phases, "ok": score2["ok"], "error_class": None if score2["ok"] else score2["error_class"]}


def scenario_4(ctx: TrialContext) -> dict[str, Any]:
    messages1 = [{"role": "user", "content": "Look up record REC-404. If the tool reports an error, answer exactly: LOOKUP_FAILED REC-404"}]
    resp1 = ctx.evaluator.post_chat(ctx, "phase1_fetch_record", messages1, BASE_TOOLS)
    score1 = classify_tool_call(resp1, "fetch_record", {"record_id": "REC-404"})
    phases = [{"name": "phase1_fetch_record", "response_path": resp1["response_path"], "request_path": resp1["request_path"], "score": score1}]
    if not score1["ok"]:
        return {"phases": phases, "ok": False, "error_class": score1["error_class"]}
    messages2 = [
        messages1[0],
        assistant_tool_message_from(resp1),
        {"role": "tool", "tool_call_id": first_call_id(resp1), "content": json.dumps({"error": "record_not_found", "message": "REC-404 does not exist"})},
    ]
    resp2 = ctx.evaluator.post_chat(ctx, "phase2_error_answer", messages2, BASE_TOOLS)
    def pred(content: str) -> bool:
        return content.strip() == "LOOKUP_FAILED REC-404"
    score2 = no_tool_answer(resp2, pred, "expected exact failure acknowledgement with no invented record details")
    phases.append({"name": "phase2_error_answer", "response_path": resp2["response_path"], "request_path": resp2["request_path"], "score": score2})
    return {"phases": phases, "ok": score2["ok"], "error_class": None if score2["ok"] else score2["error_class"]}


def scenario_5(ctx: TrialContext) -> dict[str, Any]:
    messages1 = [{"role": "user", "content": "Look up ticket DEMO-42. After the tool result, answer exactly: Ticket DEMO-42 is closed, owned by Rina, and was updated on 2026-09-05."}]
    resp1 = ctx.evaluator.post_chat(ctx, "phase1_lookup_ticket", messages1, BASE_TOOLS)
    score1 = classify_tool_call(resp1, "lookup_ticket", {"ticket_id": "DEMO-42"})
    phases = [{"name": "phase1_lookup_ticket", "response_path": resp1["response_path"], "request_path": resp1["request_path"], "score": score1}]
    if not score1["ok"]:
        return {"phases": phases, "ok": False, "error_class": score1["error_class"]}
    messages2 = [
        messages1[0],
        assistant_tool_message_from(resp1),
        {"role": "tool", "tool_call_id": first_call_id(resp1), "content": json.dumps({"ticket_id": "DEMO-42", "status": "closed", "owner": "Rina", "updated": "2026-09-05", "summary": "Password reset login failure fixed."})},
    ]
    resp2 = ctx.evaluator.post_chat(ctx, "phase2_answer_stop", messages2, BASE_TOOLS)
    def pred(content: str) -> bool:
        return content.strip() == "Ticket DEMO-42 is closed, owned by Rina, and was updated on 2026-09-05."
    score2 = no_tool_answer(resp2, pred, "expected the exact final answer derived from the mock tool result")
    phases.append({"name": "phase2_answer_stop", "response_path": resp2["response_path"], "request_path": resp2["request_path"], "score": score2})
    return {"phases": phases, "ok": score2["ok"], "error_class": None if score2["ok"] else score2["error_class"]}


def scenario_6(ctx: TrialContext) -> dict[str, Any]:
    resp = ctx.evaluator.post_chat(ctx, "single", [{"role": "user", "content": "Question: what word comes after alpha in the Greek alphabet? Answer with one word. Do not use tools."}], BASE_TOOLS)
    def pred(content: str) -> bool:
        normalized = re.sub(r"[^a-z]", "", content.lower())
        return normalized == "beta"
    score = no_tool_answer(resp, pred, "expected answer 'beta' with no tool call")
    return {"phases": [{"name": "single", "response_path": resp["response_path"], "request_path": resp["request_path"], "score": score}], "ok": score["ok"], "error_class": score["error_class"]}


SCENARIOS: dict[str, Callable[[TrialContext], dict[str, Any]]] = {
    "s1_select_correct_tool": scenario_1,
    "s2_preserve_identifiers_types": scenario_2,
    "s3_second_tool_from_first_result": scenario_3,
    "s4_mock_tool_error": scenario_4,
    "s5_answer_from_tool_data_stop": scenario_5,
    "s6_no_tool_needed": scenario_6,
}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", default="http://localhost:8080")
    ap.add_argument("--model", required=True)
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--attempts", type=int, default=5)
    ap.add_argument("--timeout", type=int, default=180)
    ap.add_argument(
        "--capture-server-metadata",
        action="store_true",
        help="Save /v1/models, /props and /slots; these may expose local paths or launch details.",
    )
    args = ap.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    ev = Evaluator(
        args.base_url,
        args.model,
        out_dir,
        attempts=args.attempts,
        timeout=args.timeout,
        capture_server_metadata=args.capture_server_metadata,
    )
    ev.save_baseline()

    results_path = out_dir / "trials.jsonl"
    with results_path.open("w", encoding="utf-8") as fp:
        for s_index, (scenario_id, func) in enumerate(SCENARIOS.items(), start=1):
            for attempt in range(1, args.attempts + 1):
                seed = 910000 + s_index * 100 + attempt
                ctx = TrialContext(ev, scenario_id, attempt, seed)
                started = time.time()
                try:
                    result = func(ctx)
                except Exception as exc:
                    result = {"ok": False, "error_class": "evaluator_error", "detail": f"{type(exc).__name__}: {exc}", "phases": []}
                row = {
                    "scenario": scenario_id,
                    "attempt": attempt,
                    "seed": seed,
                    "ok": bool(result.get("ok")),
                    "error_class": result.get("error_class"),
                    "elapsed_s": time.time() - started,
                    "phases": result.get("phases", []),
                }
                ev.results.append(row)
                fp.write(json.dumps(row, ensure_ascii=False) + "\n")
                fp.flush()
                print(f"{scenario_id} attempt {attempt}: ok={row['ok']} error={row['error_class']} elapsed={row['elapsed_s']:.2f}s")

    total = len(ev.results)
    ok = sum(1 for r in ev.results if r["ok"])
    by_scenario: dict[str, dict[str, Any]] = {}
    by_error: dict[str, int] = {}
    for r in ev.results:
        sid = r["scenario"]
        by_scenario.setdefault(sid, {"total": 0, "ok": 0, "errors": {}})
        by_scenario[sid]["total"] += 1
        if r["ok"]:
            by_scenario[sid]["ok"] += 1
        err = r.get("error_class") or "ok"
        by_scenario[sid]["errors"][err] = by_scenario[sid]["errors"].get(err, 0) + 1
        by_error[err] = by_error.get(err, 0) + 1
    summary = {"total": total, "ok": ok, "pass_rate": ok / total if total else 0, "by_scenario": by_scenario, "by_error": by_error, "results_path": str(results_path), "raw_dir": str(ev.raw_dir)}
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

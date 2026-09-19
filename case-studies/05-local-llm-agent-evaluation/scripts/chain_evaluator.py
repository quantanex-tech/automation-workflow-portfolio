#!/usr/bin/env python3
"""Long-chain evaluator for an OpenAI-compatible tool-calling endpoint.

Runs N direct llama.cpp API conversations. Each run requires exactly M sequential
mock tool calls using tool_choice=auto, then one final no-tool answer. Every raw
request and response is saved locally. Generated tool calls are never executed;
the harness validates parsed JSON arguments and injects deterministic mock tool
results.
The endpoint defaults to localhost; pass --base-url and --model explicitly as needed.
"""
from __future__ import annotations

import argparse
import json
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REQUEST_PARAMS = {
    "tool_choice": "auto",
    "parallel_tool_calls": False,
    "temperature": 0.6,
    "top_p": 0.95,
    "top_k": 20,
    "repeat_penalty": 1.05,
    "max_tokens": 768,
    "stream": False,
}

TOOL = {
    "type": "function",
    "function": {
        "name": "advance_chain",
        "description": "Advance a deterministic multi-step evaluation chain. Use the exact current token and next step number.",
        "parameters": {
            "type": "object",
            "properties": {
                "run_id": {"type": "string", "description": "Exact run identifier."},
                "step": {"type": "integer", "description": "Current chain step number."},
                "token": {"type": "string", "description": "Exact current chain token from the prior instruction or tool result."},
            },
            "required": ["run_id", "step", "token"],
            "additionalProperties": False,
        },
    },
}

DISTRACTOR_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "lookup_ticket",
            "description": "Look up a support ticket by id. Not used for chain advancement.",
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
            "name": "summarize_chain",
            "description": "Summarize a completed chain. Do not call this during the step-by-step chain; final answer should be plain text.",
            "parameters": {
                "type": "object",
                "properties": {"run_id": {"type": "string"}},
                "required": ["run_id"],
                "additionalProperties": False,
            },
        },
    },
]

TOOLS = [TOOL, *DISTRACTOR_TOOLS]


def token_for(run_number: int, step: int) -> str:
    """Token expected before a given step.

    step=1 consumes START; subsequent steps consume the token returned by the
    previous mock tool result.
    """
    if step == 1:
        return "START"
    return f"CHAIN-R{run_number:02d}-S{step - 1:02d}-K{(run_number * 97 + (step - 1) * 193) % 10000:04d}"


def next_token_for(run_number: int, step: int) -> str:
    return f"CHAIN-R{run_number:02d}-S{step:02d}-K{(run_number * 97 + step * 193) % 10000:04d}"


def request_user_prompt(run_id: str, chain_length: int) -> str:
    return (
        f"Run {run_id}: perform a {chain_length}-step tool chain. "
        "Start by calling advance_chain with step=1 and token=START. "
        "After each tool result, call advance_chain again using exactly the returned next_step and next_token. "
        f"Continue until you have successfully called step={chain_length}. "
        f"After the step {chain_length} tool result, stop calling tools and answer with exactly: COMPLETE {run_id}. "
        "Do not skip steps, do not call other tools, and preserve run_id/token strings exactly."
    )


def choice(resp: dict[str, Any]) -> dict[str, Any]:
    return (((resp.get("json") or {}).get("choices") or [{}])[0]) if isinstance(resp.get("json"), dict) else {}


def message(resp: dict[str, Any]) -> dict[str, Any]:
    return choice(resp).get("message") or {}


def finish_reason(resp: dict[str, Any]) -> str | None:
    return choice(resp).get("finish_reason")


def parse_arguments(call: dict[str, Any]) -> tuple[dict[str, Any] | None, str | None, Any]:
    raw = (call.get("function") or {}).get("arguments")
    if isinstance(raw, dict):
        return raw, None, raw
    if isinstance(raw, str):
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError as exc:
            return None, f"arguments_not_json: {exc}", raw
        if not isinstance(parsed, dict):
            return None, f"arguments_not_object: {type(parsed).__name__}", raw
        return parsed, None, raw
    return None, f"arguments_unexpected_type: {type(raw).__name__}", raw


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


class ChainEvaluator:
    def __init__(
        self,
        base_url: str,
        model: str,
        out_dir: Path,
        runs: int,
        chain_length: int,
        timeout: int,
        capture_server_metadata: bool = False,
    ):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.out_dir = out_dir
        self.raw_dir = out_dir / "raw"
        self.runs = runs
        self.chain_length = chain_length
        self.timeout = timeout
        self.capture_server_metadata = capture_server_metadata
        self.raw_dir.mkdir(parents=True, exist_ok=True)

    def get_json(self, path: str) -> Any:
        req = urllib.request.Request(self.base_url + path, headers={"Accept": "application/json", "User-Agent": "local-chain-eval"})
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read().decode("utf-8", "replace"))

    def save_baseline(self) -> dict[str, Any]:
        baseline: dict[str, Any] = {
            "created_at": datetime.now(timezone.utc).isoformat(),
            "base_url": self.base_url,
            "model": self.model,
            "runs": self.runs,
            "chain_length": self.chain_length,
            "request_params": REQUEST_PARAMS,
            "scored_tool_choice": "auto",
            "generated_actions_executed": False,
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

    def post_chat(self, run_number: int, phase: str, messages: list[dict[str, Any]], seed: int) -> dict[str, Any]:
        payload = {
            "model": self.model,
            "messages": messages,
            "tools": TOOLS,
            "seed": seed,
            **REQUEST_PARAMS,
        }
        prefix = f"run-{run_number:02d}_{phase}"
        req_path = self.raw_dir / f"{prefix}_request.json"
        resp_path = self.raw_dir / f"{prefix}_response.json"
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
                saved = {"http_status": r.status, "elapsed_s": time.time() - started, "json": json.loads(raw)}
        except urllib.error.HTTPError as exc:
            saved = {"http_status": exc.code, "elapsed_s": time.time() - started, "error_body": exc.read().decode("utf-8", "replace")}
        except Exception as exc:
            saved = {"transport_error": type(exc).__name__, "message": str(exc), "elapsed_s": time.time() - started}
        resp_path.write_text(json.dumps(saved, indent=2, ensure_ascii=False), encoding="utf-8")
        return {"request_path": str(req_path), "response_path": str(resp_path), **saved}

    def score_step(self, resp: dict[str, Any], expected_args: dict[str, Any]) -> dict[str, Any]:
        if "transport_error" in resp or "error_body" in resp:
            return {"ok": False, "error_class": "transport_failure", "detail": resp.get("message") or (resp.get("error_body") or "")[:500], "finish_reason": finish_reason(resp)}
        msg = message(resp)
        calls = msg.get("tool_calls") or []
        if not calls:
            return {
                "ok": False,
                "error_class": "tool_format_error",
                "detail": "no parsed message.tool_calls",
                "finish_reason": finish_reason(resp),
                "content_prefix": (msg.get("content") or "")[:1000],
                "completion_tokens": (((resp.get("json") or {}).get("usage") or {}).get("completion_tokens")),
            }
        if len(calls) != 1:
            return {"ok": False, "error_class": "wrong_action", "detail": f"expected exactly 1 call, got {len(calls)}", "finish_reason": finish_reason(resp), "tool_calls": calls}
        call = calls[0]
        name = (call.get("function") or {}).get("name")
        if name != "advance_chain":
            return {"ok": False, "error_class": "wrong_action", "detail": f"expected advance_chain, got {name}", "finish_reason": finish_reason(resp), "tool_calls": calls}
        args, err, raw_args = parse_arguments(call)
        if err:
            return {"ok": False, "error_class": "tool_format_error", "detail": err, "finish_reason": finish_reason(resp), "tool_calls": calls, "raw_arguments": raw_args}
        if not json_equal_strict(args, expected_args):
            return {
                "ok": False,
                "error_class": "wrong_arguments",
                "detail": f"expected parsed args {expected_args!r}, got {args!r}",
                "finish_reason": finish_reason(resp),
                "tool_calls": calls,
                "parsed_arguments": args,
            }
        if finish_reason(resp) != "tool_calls":
            return {"ok": False, "error_class": "tool_format_error", "detail": f"tool call parsed but finish_reason={finish_reason(resp)!r}", "finish_reason": finish_reason(resp), "tool_calls": calls, "parsed_arguments": args}
        return {"ok": True, "error_class": None, "detail": "matched", "finish_reason": finish_reason(resp), "tool_calls": calls, "parsed_arguments": args}

    def score_final(self, resp: dict[str, Any], run_id: str) -> dict[str, Any]:
        if "transport_error" in resp or "error_body" in resp:
            return {"ok": False, "error_class": "transport_failure", "detail": resp.get("message") or (resp.get("error_body") or "")[:500], "finish_reason": finish_reason(resp)}
        msg = message(resp)
        calls = msg.get("tool_calls") or []
        content = (msg.get("content") or "").strip()
        expected = f"COMPLETE {run_id}"
        if calls:
            return {"ok": False, "error_class": "wrong_action", "detail": f"expected final answer, got {len(calls)} tool call(s)", "finish_reason": finish_reason(resp), "tool_calls": calls, "content_prefix": content[:500]}
        if finish_reason(resp) != "stop":
            return {"ok": False, "error_class": "tool_format_error", "detail": f"expected finish_reason='stop', got {finish_reason(resp)!r}", "finish_reason": finish_reason(resp), "content_prefix": content[:500]}
        if content != expected:
            return {"ok": False, "error_class": "wrong_answer", "detail": f"expected {expected!r}, got {content!r}", "finish_reason": finish_reason(resp), "content_prefix": content[:500]}
        return {"ok": True, "error_class": None, "detail": "final answer matched", "finish_reason": finish_reason(resp), "content": content}

    def run_one(self, run_number: int) -> dict[str, Any]:
        run_id = f"CHAIN-R{run_number:02d}"
        messages: list[dict[str, Any]] = [{"role": "user", "content": request_user_prompt(run_id, self.chain_length)}]
        phases: list[dict[str, Any]] = []
        completed_steps = 0
        first_failure: dict[str, Any] | None = None

        for step in range(1, self.chain_length + 1):
            expected = {"run_id": run_id, "step": step, "token": token_for(run_number, step)}
            seed = 920000 + run_number * 100 + step
            resp = self.post_chat(run_number, f"step-{step:02d}", messages, seed)
            score = self.score_step(resp, expected)
            phase = {"phase": f"step-{step:02d}", "step": step, "seed": seed, "request_path": resp["request_path"], "response_path": resp["response_path"], "elapsed_s": resp.get("elapsed_s"), "score": score}
            phases.append(phase)
            if not score["ok"]:
                first_failure = phase
                break
            completed_steps = step
            call = (score.get("tool_calls") or [{}])[0]
            tool_call_id = call.get("id") or f"call_step_{step}"
            messages.append({"role": "assistant", "content": message(resp).get("content") or "", "tool_calls": [call]})
            tool_result = {
                "run_id": run_id,
                "completed_step": step,
                "next_step": step + 1 if step < self.chain_length else None,
                "next_token": next_token_for(run_number, step) if step < self.chain_length else None,
                "status": "continue" if step < self.chain_length else "complete",
                "instruction": (
                    f"Call advance_chain with run_id={run_id}, step={step + 1}, token={next_token_for(run_number, step)}."
                    if step < self.chain_length else
                    f"All {self.chain_length} steps complete. Stop calling tools and answer exactly: COMPLETE {run_id}"
                ),
            }
            messages.append({"role": "tool", "tool_call_id": tool_call_id, "content": json.dumps(tool_result, ensure_ascii=False)})

        final_score = None
        if completed_steps == self.chain_length and first_failure is None:
            seed = 920000 + run_number * 100 + 99
            resp = self.post_chat(run_number, "final", messages, seed)
            final_score = self.score_final(resp, run_id)
            phases.append({"phase": "final", "step": None, "seed": seed, "request_path": resp["request_path"], "response_path": resp["response_path"], "elapsed_s": resp.get("elapsed_s"), "score": final_score})
            if not final_score["ok"]:
                first_failure = phases[-1]

        return {
            "run_number": run_number,
            "run_id": run_id,
            "planned_tool_calls": self.chain_length,
            "completed_tool_calls": completed_steps,
            "ok": first_failure is None and completed_steps == self.chain_length and bool(final_score and final_score["ok"]),
            "first_failure": first_failure,
            "phases": phases,
        }


def summarize(results: list[dict[str, Any]], out_dir: Path) -> dict[str, Any]:
    total = len(results)
    ok = sum(1 for r in results if r["ok"])
    completed_tool_calls = sum(int(r.get("completed_tool_calls") or 0) for r in results)
    planned_tool_calls = sum(int(r.get("planned_tool_calls") or 0) for r in results)
    attempted_tool_calls = sum(
        1 for r in results for phase in r.get("phases", []) if phase.get("step") is not None
    )
    incorrect_calls = attempted_tool_calls - completed_tool_calls
    unattempted_calls = planned_tool_calls - attempted_tool_calls
    by_error: dict[str, int] = {}
    by_step: dict[str, int] = {}
    failure_details = []
    for r in results:
        ff = r.get("first_failure")
        if not ff:
            by_error["ok"] = by_error.get("ok", 0) + 1
            continue
        score = ff.get("score") or {}
        err = score.get("error_class") or "unknown"
        by_error[err] = by_error.get(err, 0) + 1
        step_key = str(ff.get("phase"))
        by_step[step_key] = by_step.get(step_key, 0) + 1
        failure_details.append({
            "run_number": r.get("run_number"),
            "run_id": r.get("run_id"),
            "completed_tool_calls": r.get("completed_tool_calls"),
            "failed_phase": ff.get("phase"),
            "seed": ff.get("seed"),
            "response_path": ff.get("response_path"),
            "request_path": ff.get("request_path"),
            "error_class": err,
            "finish_reason": score.get("finish_reason"),
            "detail": score.get("detail"),
            "parsed_arguments": score.get("parsed_arguments"),
            "content_prefix": score.get("content_prefix"),
        })
    summary = {
        "total_runs": total,
        "ok_runs": ok,
        "run_pass_rate": ok / total if total else 0,
        "planned_tool_calls": planned_tool_calls,
        "attempted_tool_calls": attempted_tool_calls,
        "strict_correct_calls": completed_tool_calls,
        "incorrect_calls": incorrect_calls,
        "unattempted_after_first_failure": unattempted_calls,
        "strict_correct_rate_of_attempted_calls": completed_tool_calls / attempted_tool_calls if attempted_tool_calls else 0,
        "by_error": by_error,
        "by_failed_phase": by_step,
        "failure_details": failure_details,
        "results_path": str(out_dir / "runs.jsonl"),
        "raw_dir": str(out_dir / "raw"),
    }
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    return summary


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://localhost:8080")
    parser.add_argument("--model", required=True)
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--runs", type=int, default=30)
    parser.add_argument("--chain-length", type=int, default=15)
    parser.add_argument("--timeout", type=int, default=180)
    parser.add_argument(
        "--capture-server-metadata",
        action="store_true",
        help="Save /v1/models, /props and /slots; these may expose local paths or launch details.",
    )
    args = parser.parse_args()

    out_dir = Path(args.out_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    evaluator = ChainEvaluator(
        args.base_url,
        args.model,
        out_dir,
        args.runs,
        args.chain_length,
        args.timeout,
        capture_server_metadata=args.capture_server_metadata,
    )
    evaluator.save_baseline()

    results = []
    runs_path = out_dir / "runs.jsonl"
    with runs_path.open("w", encoding="utf-8") as fp:
        for run_number in range(1, args.runs + 1):
            started = time.time()
            try:
                row = evaluator.run_one(run_number)
            except Exception as exc:
                row = {
                    "run_number": run_number,
                    "run_id": f"CHAIN-R{run_number:02d}",
                    "planned_tool_calls": args.chain_length,
                    "completed_tool_calls": 0,
                    "ok": False,
                    "first_failure": {"phase": "evaluator", "score": {"error_class": "evaluator_error", "detail": f"{type(exc).__name__}: {exc}"}},
                    "phases": [],
                }
            row["elapsed_s"] = time.time() - started
            results.append(row)
            fp.write(json.dumps(row, ensure_ascii=False) + "\n")
            fp.flush()
            ff = row.get("first_failure")
            if ff:
                score = ff.get("score") or {}
                print(f"run {run_number:02d}: ok=False completed={row.get('completed_tool_calls')}/{args.chain_length} failed={ff.get('phase')} error={score.get('error_class')} finish={score.get('finish_reason')} elapsed={row['elapsed_s']:.2f}s")
            else:
                print(f"run {run_number:02d}: ok=True completed={row.get('completed_tool_calls')}/{args.chain_length} elapsed={row['elapsed_s']:.2f}s")

    summary = summarize(results, out_dir)
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

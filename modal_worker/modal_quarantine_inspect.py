"""Read-only Modal inspection for quarantined Creator Tops.

This script never launches, retries, cancels, deploys, deletes, or mutates Modal
resources. It reads historical App metadata/logs and Function-call history,
polls existing FunctionCalls, and—only when an already-completed result is still
retrievable—copies the returned paid source art into the GitHub Actions workspace
for evidence banking.
"""
from __future__ import annotations

import base64
import json
import os
import re
import subprocess
from pathlib import Path
from typing import Any

import modal

ROOT = Path(__file__).resolve().parents[1]
TRIGGER = ROOT / "modal_worker" / "modal_quarantine_inspect_trigger.json"
OUT = ROOT / "modal-quarantine-inspection-output"
APP_RE = re.compile(r"\b(ap-[A-Za-z0-9]+)\b")
FU_RE = re.compile(r"\b(fu-[A-Za-z0-9]+)\b")
FC_RE = re.compile(r"\b(fc-[A-Za-z0-9]+)\b")


def _safe_text(value: object, limit: int = 800) -> str:
    text = str(value)
    token_id = os.environ.get("MODAL_TOKEN_ID")
    token_secret = os.environ.get("MODAL_TOKEN_SECRET")
    if token_id:
        text = text.replace(token_id, "<redacted>")
    if token_secret:
        text = text.replace(token_secret, "<redacted>")
    return text[:limit]


def _modal_cmd(args: list[str], timeout: int = 90) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["NO_COLOR"] = "1"
    return subprocess.run(args, text=True, capture_output=True, env=env, timeout=timeout)


def _combined_output(proc: subprocess.CompletedProcess[str]) -> str:
    return (proc.stdout or "") + (("\n[stderr]\n" + proc.stderr) if proc.stderr else "")


def _recursive_ids(value: Any, regex: re.Pattern[str]) -> set[str]:
    found: set[str] = set()
    if isinstance(value, dict):
        for k, v in value.items():
            found.update(regex.findall(str(k)))
            found.update(_recursive_ids(v, regex))
    elif isinstance(value, (list, tuple)):
        for item in value:
            found.update(_recursive_ids(item, regex))
    elif value is not None:
        found.update(regex.findall(str(value)))
    return found


def _flatten_graph(nodes: list[Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []

    def walk(node: Any) -> None:
        status = getattr(node, "status", None)
        out.append(
            {
                "input_id": getattr(node, "input_id", None),
                "function_call_id": getattr(node, "function_call_id", None),
                "task_id": getattr(node, "task_id", None),
                "status": getattr(status, "name", str(status) if status is not None else None),
                "function_name": getattr(node, "function_name", None),
                "module_name": getattr(node, "module_name", None),
            }
        )
        for child in getattr(node, "children", []) or []:
            walk(child)

    for n in nodes:
        walk(n)
    return out


def _result_summary(result: Any) -> dict[str, Any]:
    summary: dict[str, Any] = {"python_type": type(result).__name__}
    if isinstance(result, dict):
        summary["keys"] = sorted(str(k) for k in result.keys())
        directions = result.get("directions")
        summary["creator_tops_payload"] = bool(
            isinstance(result.get("reference_png"), str)
            and isinstance(directions, list)
            and len(directions) == 4
        )
    elif isinstance(result, (bytes, bytearray, str, list, tuple)):
        summary["length"] = len(result)
    return summary


def _bank_creator_tops_result(style: int, fc_id: str, result: dict[str, Any], target: Path) -> dict[str, Any]:
    recovered = target / "recovered-paid-sources"
    recovered.mkdir(parents=True, exist_ok=True)
    ref = base64.b64decode(result["reference_png"], validate=True)
    (recovered / "reference.png").write_bytes(ref)
    directions: list[str] = []
    for item in result["directions"]:
        name = str(item["direction"])
        raw = base64.b64decode(item["png"], validate=True)
        (recovered / f"{name}.png").write_bytes(raw)
        directions.append(name)
    metadata = {
        "schema": "plushbound.modal_quarantine_recovered_paid_sources.v1",
        "style_index": style,
        "function_call_id": fc_id,
        "source": "existing_modal_functioncall_result",
        "new_paid_render_launched": False,
        "reference_present": True,
        "directions": sorted(directions),
        "model": result.get("model"),
        "reference_seed": result.get("reference_seed"),
        "reference_seconds": result.get("reference_seconds"),
    }
    (recovered / "recovery-metadata.json").write_text(json.dumps(metadata, indent=2, sort_keys=True) + "\n")
    return metadata


def _inspect_function_call(style: int, fc_id: str, target: Path) -> dict[str, Any]:
    item: dict[str, Any] = {"function_call_id": fc_id}
    call = modal.FunctionCall.from_id(fc_id)
    try:
        item["num_inputs"] = call.num_inputs()
    except Exception as exc_num:
        item["num_inputs_error"] = {"type": type(exc_num).__name__, "message": _safe_text(exc_num)}
    try:
        item["call_graph"] = _flatten_graph(call.get_call_graph())
    except Exception as exc_graph:
        item["call_graph_error"] = {"type": type(exc_graph).__name__, "message": _safe_text(exc_graph)}
    try:
        tail = []
        for entry in call.logs.tail(entries=100):
            tail.append(
                {
                    "timestamp": entry.timestamp.isoformat() if getattr(entry, "timestamp", None) else None,
                    "source": getattr(getattr(entry, "source", None), "value", str(getattr(entry, "source", ""))),
                    "message": _safe_text(getattr(entry, "message", ""), 4000),
                }
            )
        item["log_tail"] = tail
    except Exception as exc_logs:
        item["log_tail_error"] = {"type": type(exc_logs).__name__, "message": _safe_text(exc_logs)}
    try:
        result = call.get(timeout=0)
        item["poll_state"] = "result_available"
        item["result_summary"] = _result_summary(result)
        if isinstance(result, dict) and item["result_summary"].get("creator_tops_payload"):
            item["recovered_paid_sources"] = _bank_creator_tops_result(style, fc_id, result, target)
    except Exception as exc_get:
        item["poll_state"] = "no_result_returned"
        item["poll_error"] = {"type": type(exc_get).__name__, "message": _safe_text(exc_get)}
    return item


def inspect_style(style: int) -> dict[str, Any]:
    exc_path = ROOT / "modal_worker" / f"creator_tops_exception_{style:03d}.json"
    exc = json.loads(exc_path.read_text())
    if exc.get("automatic_retry_allowed") is not False or exc.get("blocks_tops_completion_contract") is not True:
        raise RuntimeError(f"style {style:03d} is not an unresolved fail-closed quarantine")
    match = APP_RE.search(str(exc.get("modal_run_url", "")))
    if not match:
        raise RuntimeError(f"style {style:03d} has no Modal app ID in modal_run_url")
    app_id = match.group(1)
    target = OUT / f"style-{style:03d}"
    target.mkdir(parents=True, exist_ok=True)

    logs_proc = _modal_cmd(
        [
            "modal", "app", "logs", app_id,
            "--tail", "1000",
            "--timestamps",
            "--show-function-id",
            "--show-function-call-id",
            "--show-container-id",
        ]
    )
    app_log = _combined_output(logs_proc)
    (target / "app.log").write_text(app_log)

    info_proc = _modal_cmd(["modal", "app", "info", app_id, "--json", "--no-color"])
    info_text = _combined_output(info_proc)
    (target / "app-info.txt").write_text(info_text)
    try:
        app_info: Any = json.loads(info_proc.stdout or "null")
    except json.JSONDecodeError:
        app_info = None

    function_ids = set(FU_RE.findall(app_log))
    function_ids.update(FU_RE.findall(info_text))
    function_ids.update(_recursive_ids(app_info, FU_RE))
    fc_ids = set(FC_RE.findall(app_log))
    fc_ids.update(FC_RE.findall(info_text))
    fc_ids.update(_recursive_ids(app_info, FC_RE))

    function_histories: list[dict[str, Any]] = []
    for fu_id in sorted(function_ids):
        calls_proc = _modal_cmd(
            [
                "modal", "function", "calls", fu_id,
                "--tail", "1000",
                "--show-function-call-id",
                "--json",
                "--no-color",
            ]
        )
        calls_text = _combined_output(calls_proc)
        safe_name = fu_id.replace("/", "_")
        (target / f"function-calls-{safe_name}.txt").write_text(calls_text)
        try:
            calls_json: Any = json.loads(calls_proc.stdout or "null")
        except json.JSONDecodeError:
            calls_json = None
        discovered = set(FC_RE.findall(calls_text))
        discovered.update(_recursive_ids(calls_json, FC_RE))
        fc_ids.update(discovered)
        function_histories.append(
            {
                "function_id": fu_id,
                "exit_code": calls_proc.returncode,
                "function_call_ids": sorted(discovered),
                "json": calls_json,
            }
        )

    function_calls = [_inspect_function_call(style, fc_id, target) for fc_id in sorted(fc_ids)]
    usable_recovered = any("recovered_paid_sources" in item for item in function_calls)
    statuses = {
        n.get("status")
        for item in function_calls
        for n in item.get("call_graph", [])
        if n.get("status")
    }
    app_log_lower = app_log.lower()
    scheduling_wait_only = (
        "waiting to be scheduled on a gpu" in app_log_lower
        and "stopping app - local client disconnected" in app_log_lower
        and not any("SUCCESS" == s for s in statuses)
    )

    if usable_recovered:
        remote_state = "completed_result_recovered"
    elif "PENDING" in statuses:
        remote_state = "running_or_queued"
    elif statuses & {"FAILURE", "INIT_FAILURE", "TERMINATED", "TIMEOUT"}:
        remote_state = "failed_or_terminated_after_launch"
    elif statuses and statuses <= {"SUCCESS"}:
        remote_state = "completed_but_result_unavailable_or_unrecognized"
    elif scheduling_wait_only:
        remote_state = "capacity_wait_ended_on_client_disconnect"
    elif not fc_ids:
        remote_state = "no_function_call_id_observed"
    else:
        remote_state = "ambiguous"

    report: dict[str, Any] = {
        "style_index": style,
        "app_id": app_id,
        "modal_app_logs_exit_code": logs_proc.returncode,
        "modal_app_info_exit_code": info_proc.returncode,
        "function_ids": sorted(function_ids),
        "function_histories": function_histories,
        "function_call_ids": sorted(fc_ids),
        "function_calls": function_calls,
        "usable_paid_output_recovered": usable_recovered,
        "remote_evidence_state": remote_state,
        "scheduling_wait_only_observed": scheduling_wait_only,
        "automatic_retry_allowed": False,
        "duplicate_paid_retry_safe": False,
    }
    (target / "inspection.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    return report


def main() -> None:
    trigger = json.loads(TRIGGER.read_text())
    assert trigger["schema"] == "plushbound.modal_quarantine_inspect_trigger.v1"
    assert trigger["read_only"] is True
    styles = [int(x) for x in trigger["style_indices"]]
    assert styles and len(styles) == len(set(styles))
    OUT.mkdir(parents=True, exist_ok=True)
    reports = [inspect_style(style) for style in styles]
    summary = {
        "schema": "plushbound.modal_quarantine_inspection.v2",
        "read_only": True,
        "new_paid_render_launched": False,
        "styles": reports,
        "recovered_styles": [r["style_index"] for r in reports if r["usable_paid_output_recovered"]],
        "automatic_retry_authorized": False,
    }
    (OUT / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

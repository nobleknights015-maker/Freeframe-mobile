"""Read-only Modal operations MCP for FreeFrame / Plushbound production.

The server is intentionally evidence-first. It exposes observability and billing
information, but no launch, retry, cancellation, deployment, or mutation tools.
That keeps the Plushbound production rail fail-closed when paid work is uncertain.
"""
from __future__ import annotations

import dataclasses
import datetime as dt
import decimal
import enum
import math
from typing import Any

import modal

APP_NAME = "freeframe-modal-ops"
ALLOWED_APP_PREFIXES = ("freeframe-", "plushbound-")
MAX_LOG_ENTRIES = 250

image = modal.Image.debian_slim(python_version="3.11").pip_install(
    "fastmcp>=3.1,<4",
    "modal>=1.6.2,<2",
)
app = modal.App(APP_NAME)


def _is_allowed_app(name: str) -> bool:
    value = str(name or "").strip()
    return bool(value) and value.startswith(ALLOWED_APP_PREFIXES)


def _jsonable(value: Any, *, depth: int = 0) -> Any:
    """Convert Modal SDK metadata into a bounded JSON-compatible value."""
    if depth > 8:
        return repr(value)
    if value is None or isinstance(value, (str, int, bool)):
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else str(value)
    if isinstance(value, decimal.Decimal):
        return str(value)
    if isinstance(value, (dt.datetime, dt.date, dt.time)):
        return value.isoformat()
    if isinstance(value, enum.Enum):
        return _jsonable(value.value, depth=depth + 1)
    if dataclasses.is_dataclass(value):
        return _jsonable(dataclasses.asdict(value), depth=depth + 1)
    if isinstance(value, dict):
        return {str(k): _jsonable(v, depth=depth + 1) for k, v in value.items()}
    if isinstance(value, (list, tuple, set, frozenset)):
        return [_jsonable(v, depth=depth + 1) for v in value]
    if hasattr(value, "model_dump"):
        try:
            return _jsonable(value.model_dump(), depth=depth + 1)
        except Exception:
            pass
    if hasattr(value, "__dict__"):
        data = {key: val for key, val in vars(value).items() if not key.startswith("_")}
        if data:
            return _jsonable(data, depth=depth + 1)
    return repr(value)


def _bounded_logs(entries: Any, *, limit: int) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for entry in entries:
        item = _jsonable(entry)
        if not isinstance(item, dict):
            item = {"message": str(item)}
        message = str(item.get("message", ""))
        if len(message) > 12_000:
            item["message"] = message[-12_000:]
            item["message_truncated"] = True
        out.append(item)
        if len(out) >= limit:
            break
    return out


def _safe_result_summary(value: Any, *, depth: int = 0) -> Any:
    """Summarize call outputs without returning image/base64 payloads."""
    if depth > 7:
        return "<depth-limit>"
    if value is None or isinstance(value, (str, int, float, bool)):
        if isinstance(value, str) and len(value) > 4_000:
            return {"type": "string", "chars": len(value), "preview": value[:500]}
        return value
    if isinstance(value, bytes):
        return {"type": "bytes", "bytes": len(value)}
    if dataclasses.is_dataclass(value):
        return _safe_result_summary(dataclasses.asdict(value), depth=depth + 1)
    if isinstance(value, dict):
        result: dict[str, Any] = {}
        for raw_key, item in value.items():
            key = str(raw_key)
            lowered = key.lower()
            if "base64" in lowered or lowered in {"png", "image", "image_bytes", "reference_png"} or lowered.endswith("_png"):
                if isinstance(item, str):
                    result[key] = {"redacted_payload": True, "chars": len(item)}
                elif isinstance(item, bytes):
                    result[key] = {"redacted_payload": True, "bytes": len(item)}
                else:
                    result[key] = {"redacted_payload": True, "type": type(item).__name__}
                continue
            result[key] = _safe_result_summary(item, depth=depth + 1)
        return result
    if isinstance(value, (list, tuple)):
        if len(value) > 50:
            return {"type": "list", "count": len(value), "items": [_safe_result_summary(v, depth=depth + 1) for v in value[:50]], "truncated": True}
        return [_safe_result_summary(v, depth=depth + 1) for v in value]
    return _jsonable(value, depth=depth + 1)


def _clamp_logs(value: int) -> int:
    return max(1, min(int(value), MAX_LOG_ENTRIES))


def _inspect_function_call(function_call_id: str, log_tail: int) -> dict[str, Any]:
    call_id = str(function_call_id or "").strip()
    if not call_id.startswith("fc-"):
        raise ValueError("function_call_id must be a Modal FunctionCall ID beginning with 'fc-'")
    call = modal.FunctionCall.from_id(call_id)
    try:
        logs = _bounded_logs(call.logs.tail(_clamp_logs(log_tail)), limit=_clamp_logs(log_tail))
    except Exception as exc:
        logs = [{"log_lookup_error": type(exc).__name__, "message": str(exc)}]

    status = "unknown"
    result_summary = None
    error = None
    try:
        result = call.get(timeout=0)
        status = "completed"
        result_summary = _safe_result_summary(result)
    except modal.exception.OutputExpiredError as exc:
        status = "output_expired"
        error = {"type": type(exc).__name__, "message": str(exc)}
    except modal.exception.TimeoutError:
        status = "running_or_queued"
    except Exception as exc:
        status = "unknown_or_failed"
        error = {"type": type(exc).__name__, "message": str(exc)}

    return {"schema": "freeframe.modal.function_call_evidence.v1", "function_call_id": call_id, "status": status, "result_summary": result_summary, "error": error, "logs": logs}


@app.function(image=image, timeout=90)
@modal.asgi_app(requires_proxy_auth=True)
def mcp_server():
    from fastmcp import FastMCP

    mcp = FastMCP(
        "FreeFrame Modal Ops",
        instructions=("Read-only operational evidence for FreeFrame and Plushbound Modal workloads. Never infer that paid work is safe to retry from missing evidence."),
    )

    @mcp.tool
    def workspace_overview() -> dict[str, Any]:
        """List live FreeFrame/Plushbound apps in the current Modal environment."""
        env = modal.Environment.from_context()
        workspace = modal.Workspace.from_context()
        apps = []
        for app_handle in env.apps.list():
            name = str(getattr(app_handle, "name", "") or "")
            if not _is_allowed_app(name):
                continue
            try:
                apps.append({"name": name, "info": _jsonable(app_handle.info(refresh=True))})
            except Exception as exc:
                apps.append({"name": name, "info_error": {"type": type(exc).__name__, "message": str(exc)}})
        return {"schema": "freeframe.modal.workspace_overview.v1", "workspace": workspace.name, "environment": env.name, "app_prefix_allowlist": list(ALLOWED_APP_PREFIXES), "apps": apps, "read_only": True}

    @mcp.tool
    def inspect_app(app_name: str, log_tail: int = 50) -> dict[str, Any]:
        """Read lifecycle metadata and recent logs for an allowed Modal app."""
        if not _is_allowed_app(app_name):
            raise ValueError("app_name is outside the FreeFrame/Plushbound allowlist")
        remote_app = modal.App.lookup(app_name)
        limit = _clamp_logs(log_tail)
        return {"schema": "freeframe.modal.app_evidence.v1", "app_name": app_name, "info": _jsonable(remote_app.info(refresh=True)), "logs": _bounded_logs(remote_app.logs.tail(limit), limit=limit)}

    @mcp.tool
    def inspect_function(app_name: str, function_name: str, log_tail: int = 50) -> dict[str, Any]:
        """Read metadata, live stats, historical stats, and logs for a plain Modal Function."""
        if not _is_allowed_app(app_name):
            raise ValueError("app_name is outside the FreeFrame/Plushbound allowlist")
        name = str(function_name or "").strip()
        if not name:
            raise ValueError("function_name is required")
        fn = modal.Function.from_name(app_name, name)
        limit = _clamp_logs(log_tail)
        return {"schema": "freeframe.modal.function_evidence.v1", "app_name": app_name, "function_name": name, "info": _jsonable(fn.info(refresh=True)), "current_stats": _jsonable(fn.get_current_stats()), "stats": _jsonable(fn.stats()), "logs": _bounded_logs(fn.logs.tail(limit), limit=limit)}

    @mcp.tool
    def inspect_function_call(function_call_id: str, log_tail: int = 100) -> dict[str, Any]:
        """Poll one exact Modal FunctionCall by fc- ID and return redacted evidence plus logs."""
        return _inspect_function_call(function_call_id, log_tail)

    @mcp.tool
    def inspect_creator_top(style_index: int, function_call_id: str, log_tail: int = 100) -> dict[str, Any]:
        """Reconcile one Creator Top style against an exact Modal FunctionCall ID; fail closed on ambiguity."""
        style = int(style_index)
        if not 1 <= style <= 999:
            raise ValueError("style_index must be between 1 and 999")
        evidence = _inspect_function_call(function_call_id, log_tail)
        status = evidence["status"]
        retry_disposition = "do_not_retry" if status in {"completed", "running_or_queued", "output_expired"} else "manual_review_required"
        return {
            "schema": "plushbound.creator_top_modal_reconciliation.v1",
            "style_index": style,
            "logical_id": f"creator/tops/{style:03d}",
            "modal_evidence": evidence,
            "retry_disposition": retry_disposition,
            "automatic_paid_retry_authorized": False,
            "reason": "Existing or potentially existing paid work must not be duplicated." if retry_disposition == "do_not_retry" else "Evidence is not definitive enough to authorize another paid launch.",
        }

    @mcp.tool
    def billing_summary(cycle: str = "this month") -> dict[str, Any]:
        """Read Modal workspace and current-environment billing summaries."""
        cycle_value = str(cycle).strip().lower()
        if cycle_value not in {"this month", "last month"} and not (len(cycle_value) == 7 and cycle_value[4] == "-" and cycle_value.replace("-", "").isdigit()):
            raise ValueError("cycle must be 'this month', 'last month', or YYYY-MM")
        workspace = modal.Workspace.from_context()
        env = modal.Environment.from_context()
        return {"schema": "freeframe.modal.billing_summary.v1", "cycle": cycle_value, "workspace": _jsonable(workspace.billing.summary(cycle_value)), "environment": _jsonable(env.billing.summary(cycle_value))}

    return mcp.http_app(path="/mcp/", stateless_http=True)

from __future__ import annotations

import json
import os
import sys
import ipaddress
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

try:
    from app.backend.services.normalize import unsafe_import_url_reason
except Exception:  # pragma: no cover - standalone fallback if app package import is unavailable.
    def unsafe_import_url_reason(url: str) -> str | None:
        parsed = urlparse(url.strip())
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            return "URL must use http or https and include a host."
        if parsed.username or parsed.password:
            return "URL must not contain embedded credentials."
        hostname = (parsed.hostname or "").strip().lower().rstrip(".")
        if not hostname:
            return "URL must include a host."
        if hostname in {"localhost", "localhost.localdomain"} or hostname.endswith(".localhost"):
            return "localhost URLs are unsafe for job import."
        try:
            address = ipaddress.ip_address(hostname)
        except ValueError:
            return None
        if (
            address.is_loopback
            or address.is_private
            or address.is_link_local
            or address.is_multicast
            or address.is_reserved
            or address.is_unspecified
        ):
            return "local, private, metadata, or reserved IP addresses are unsafe for job import."
        return None


PROTOCOL_VERSION = "2025-03-26"
SERVER_INFO = {"name": "jobfiller-mcp", "version": "0.1.0"}
DEFAULT_API_BASE = "http://127.0.0.1:8001/api"
LOCAL_HOSTS = {"127.0.0.1", "localhost", "::1"}
ROOT = Path(__file__).resolve().parents[2]
RUNTIME_CONFIG_PATH = ROOT / "outputs" / "jobfiller-runtime.json"


JOB_RECORD_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "url": {"type": "string", "description": "Source job URL. Required."},
        "company": {"type": "string"},
        "title": {"type": "string"},
        "location": {"type": "string"},
        "work_model": {"type": "string", "description": "Remote, Hybrid, Onsite, or a concise local value."},
        "apply_url": {"type": "string"},
        "role_family": {"type": "string"},
        "key_requirements": {"type": "string", "description": "Semicolon-separated role requirements."},
        "keywords": {"type": "string", "description": "Semicolon-separated targeted keywords."},
        "fit_score": {"type": "integer", "minimum": 0, "maximum": 100},
        "notes": {"type": "string"},
        "posting_age_text": {"type": "string", "description": "Examples: 2 hours ago, 1 day ago, 3 weeks ago."},
        "raw_text": {"type": "string"},
        "materials": {"type": "string"},
        "manual_questions": {"type": "string"},
        "salary": {"type": "string"},
    },
    "required": ["url"],
    "additionalProperties": True,
}


TOOLS: list[dict[str, Any]] = [
    {
        "name": "export_jobs_to_jobfiller",
        "description": (
            "Export one or more discovered job records into the local JobFiller app. "
            "This creates or updates jobs through /api/imports/bulk and can optionally process artifacts."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "jobs": {"type": "array", "items": JOB_RECORD_SCHEMA, "minItems": 1},
                "source": {
                    "type": "string",
                    "description": "Importer label stored on each job, for example codex, claude-code, or browser-agent.",
                    "default": "mcp",
                },
                "process": {
                    "type": "boolean",
                    "description": "When true, JobFiller immediately runs missing-info checks and artifact generation.",
                    "default": False,
                },
                "api_base": {
                    "type": "string",
                    "description": "Optional local JobFiller API base URL. Defaults to JOBFILLER_API_BASE or http://127.0.0.1:8001/api.",
                },
            },
            "required": ["jobs"],
            "additionalProperties": False,
        },
    },
    {
        "name": "validate_jobfiller_export",
        "description": "Validate job records before exporting them to JobFiller. This does not call the JobFiller API.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "jobs": {"type": "array", "items": JOB_RECORD_SCHEMA, "minItems": 1},
            },
            "required": ["jobs"],
            "additionalProperties": False,
        },
    },
    {
        "name": "jobfiller_status",
        "description": "Check whether the local JobFiller API is reachable and return health/model status.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "api_base": {
                    "type": "string",
                    "description": "Optional local JobFiller API base URL. Defaults to JOBFILLER_API_BASE or http://127.0.0.1:8001/api.",
                }
            },
            "additionalProperties": False,
        },
    },
]


class ToolExecutionError(RuntimeError):
    pass


def _api_base(value: str | None = None) -> str:
    raw = (value or os.environ.get("JOBFILLER_API_BASE") or _runtime_api_base() or DEFAULT_API_BASE).strip().rstrip("/")
    parsed = urlparse(raw)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ToolExecutionError("api_base must be a valid local HTTP URL.")
    if parsed.hostname not in LOCAL_HOSTS:
        raise ToolExecutionError("api_base must point to localhost or 127.0.0.1.")
    if not parsed.path.endswith("/api"):
        raw = f"{raw}/api"
    return raw


def _runtime_api_base() -> str:
    return str(_runtime_config().get("api_base") or "").strip()


def _runtime_token() -> str:
    return str(_runtime_config().get("mutation_token") or "").strip()


def _runtime_config() -> dict[str, Any]:
    configured = os.environ.get("JOBFILLER_RUNTIME_CONFIG", "").strip()
    path = Path(configured) if configured else RUNTIME_CONFIG_PATH
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _json_request(
    method: str,
    url: str,
    body: dict[str, Any] | None = None,
    timeout: float = 20.0,
    headers: dict[str, str] | None = None,
) -> dict[str, Any]:
    data = None if body is None else json.dumps(body).encode("utf-8")
    request_headers = {"Content-Type": "application/json", "Accept": "application/json"}
    if headers:
        request_headers.update(headers)
    request = urllib.request.Request(
        url,
        data=data,
        headers=request_headers,
        method=method,
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        error_body = exc.read().decode("utf-8", errors="replace")
        raise ToolExecutionError(f"JobFiller API returned HTTP {exc.code}: {error_body}") from exc
    except urllib.error.URLError as exc:
        raise ToolExecutionError(f"Could not reach JobFiller API: {exc.reason}") from exc
    except TimeoutError as exc:
        raise ToolExecutionError("Timed out contacting JobFiller API.") from exc
    return json.loads(raw) if raw else {}


def _api_token(api_base: str) -> str:
    configured = os.environ.get("JOBFILLER_LOCAL_TOKEN", "").strip()
    if configured:
        return configured
    runtime_token = _runtime_token()
    if runtime_token:
        return runtime_token
    try:
        session = _json_request("GET", f"{api_base}/session", timeout=5.0)
    except ToolExecutionError:
        return ""
    return str(session.get("mutation_token") or "").strip()


def _validate_jobs(jobs: Any) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    if not isinstance(jobs, list):
        return [], [{"index": None, "error": "jobs must be an array"}]
    if len(jobs) > 100:
        return [], [{"index": None, "error": "jobs must contain at most 100 records per export"}]

    valid: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    for index, job in enumerate(jobs):
        if not isinstance(job, dict):
            errors.append({"index": index, "error": "job must be an object"})
            continue
        url = str(job.get("url") or job.get("source_url") or "").strip()
        if not url:
            errors.append({"index": index, "error": "job.url is required"})
            continue
        reason = unsafe_import_url_reason(url)
        if reason:
            errors.append({"index": index, "url": url, "error": reason})
            continue
        apply_url = str(job.get("apply_url") or "").strip()
        if apply_url:
            apply_reason = unsafe_import_url_reason(apply_url)
            if apply_reason:
                errors.append({"index": index, "url": apply_url, "error": f"apply_url: {apply_reason}"})
                continue
        raw_text = str(job.get("raw_text") or "")
        if len(raw_text) > 25000:
            errors.append({"index": index, "url": url, "error": "raw_text must be 25,000 characters or fewer"})
            continue
        normalized = dict(job)
        normalized["url"] = url
        valid.append(normalized)
    return valid, errors


def validate_jobfiller_export(arguments: dict[str, Any]) -> dict[str, Any]:
    valid, errors = _validate_jobs(arguments.get("jobs"))
    return {
        "valid": not errors,
        "valid_count": len(valid),
        "error_count": len(errors),
        "errors": errors,
    }


def export_jobs_to_jobfiller(arguments: dict[str, Any]) -> dict[str, Any]:
    valid, errors = _validate_jobs(arguments.get("jobs"))
    if errors:
        raise ToolExecutionError(json.dumps({"message": "Invalid job export payload.", "errors": errors}, indent=2))
    body = {
        "jobs": valid,
        "source": str(arguments.get("source") or "mcp"),
        "process": bool(arguments.get("process", False)),
    }
    api_base = _api_base(arguments.get("api_base"))
    token = _api_token(api_base)
    if not token:
        raise ToolExecutionError("Could not obtain a local JobFiller mutation token. Start JobFiller first.")
    response = _json_request("POST", f"{api_base}/imports/bulk", body, timeout=120.0, headers={"X-JobFiller-Token": token})
    return {
        "api_base": api_base,
        "submitted": len(valid),
        "response": response,
    }


def jobfiller_status(arguments: dict[str, Any]) -> dict[str, Any]:
    api_base = _api_base(arguments.get("api_base"))
    health = _json_request("GET", f"{api_base}/health", timeout=5.0)
    token = _api_token(api_base)
    protected_headers = {"X-JobFiller-Token": token} if token else {}
    try:
        model_health = _json_request("GET", f"{api_base}/model-health", timeout=5.0, headers=protected_headers)
    except ToolExecutionError as exc:
        model_health = {"status": "unavailable", "error": str(exc)}
    return {
        "api_base": api_base,
        "health": health,
        "model_health": model_health,
    }


TOOL_HANDLERS = {
    "export_jobs_to_jobfiller": export_jobs_to_jobfiller,
    "validate_jobfiller_export": validate_jobfiller_export,
    "jobfiller_status": jobfiller_status,
}


def tool_result(payload: dict[str, Any], *, is_error: bool = False) -> dict[str, Any]:
    return {
        "content": [
            {
                "type": "text",
                "text": json.dumps(payload, indent=2, sort_keys=True),
            }
        ],
        "isError": is_error,
    }


def handle_request(message: dict[str, Any]) -> dict[str, Any] | None:
    request_id = message.get("id")
    method = message.get("method")
    params = message.get("params") or {}

    if request_id is None:
        return None

    try:
        if method == "initialize":
            requested = params.get("protocolVersion") if isinstance(params, dict) else None
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {
                    "protocolVersion": requested or PROTOCOL_VERSION,
                    "capabilities": {"tools": {"listChanged": False}},
                    "serverInfo": SERVER_INFO,
                    "instructions": (
                        "Use export_jobs_to_jobfiller to send discovered job records to the local "
                        "JobFiller app. The server imports data only; it never submits applications."
                    ),
                },
            }
        if method == "ping":
            return {"jsonrpc": "2.0", "id": request_id, "result": {}}
        if method == "tools/list":
            return {"jsonrpc": "2.0", "id": request_id, "result": {"tools": TOOLS}}
        if method == "tools/call":
            name = params.get("name") if isinstance(params, dict) else None
            arguments = params.get("arguments") if isinstance(params, dict) else {}
            if name not in TOOL_HANDLERS:
                return _jsonrpc_error(request_id, -32602, f"Unknown tool: {name}")
            result = TOOL_HANDLERS[name](arguments or {})
            return {"jsonrpc": "2.0", "id": request_id, "result": tool_result(result)}
        return _jsonrpc_error(request_id, -32601, f"Method not found: {method}")
    except ToolExecutionError as exc:
        return {"jsonrpc": "2.0", "id": request_id, "result": tool_result({"error": str(exc)}, is_error=True)}
    except Exception as exc:  # keep protocol process alive for client recovery.
        return _jsonrpc_error(request_id, -32603, "Internal error", {"error": str(exc)})


def _jsonrpc_error(request_id: Any, code: int, message: str, data: dict[str, Any] | None = None) -> dict[str, Any]:
    error: dict[str, Any] = {"code": code, "message": message}
    if data:
        error["data"] = data
    return {"jsonrpc": "2.0", "id": request_id, "error": error}


def handle_message(raw: str) -> str | None:
    message = json.loads(raw)
    if isinstance(message, list):
        responses = [response for item in message if isinstance(item, dict) for response in [handle_request(item)] if response]
        return json.dumps(responses, separators=(",", ":")) if responses else None
    if not isinstance(message, dict):
        return json.dumps(_jsonrpc_error(None, -32600, "Invalid Request"), separators=(",", ":"))
    response = handle_request(message)
    return json.dumps(response, separators=(",", ":")) if response else None


def main() -> int:
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            response = handle_message(line)
        except json.JSONDecodeError as exc:
            response = json.dumps(_jsonrpc_error(None, -32700, "Parse error", {"error": str(exc)}), separators=(",", ":"))
        if response:
            sys.stdout.write(response + "\n")
            sys.stdout.flush()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

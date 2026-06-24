from __future__ import annotations

import json

import pytest

from integrations.mcp import jobfiller_mcp_server as mcp


def decode(raw: str) -> dict:
    return json.loads(raw)


def test_mcp_initialize_and_tool_list_contract() -> None:
    initialized = decode(
        mcp.handle_message(
            json.dumps(
                {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "initialize",
                    "params": {"protocolVersion": "2025-03-26", "capabilities": {}, "clientInfo": {"name": "test"}},
                }
            )
        )
    )
    assert initialized["result"]["capabilities"]["tools"]["listChanged"] is False

    listed = decode(json.dumps(mcp.handle_request({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})))
    tool_names = {tool["name"] for tool in listed["result"]["tools"]}
    assert {"export_jobs_to_jobfiller", "validate_jobfiller_export", "jobfiller_status"} <= tool_names


def test_mcp_validate_tool_reports_row_errors_without_api_call() -> None:
    response = mcp.handle_request(
        {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {
                "name": "validate_jobfiller_export",
                "arguments": {
                    "jobs": [
                        {"url": "https://example.com/jobs/backend", "company": "ExampleCo"},
                        {"company": "MissingUrlCo"},
                    ]
                },
            },
        }
    )

    assert response is not None
    result_text = response["result"]["content"][0]["text"]
    payload = json.loads(result_text)
    assert payload["valid"] is False
    assert payload["valid_count"] == 1
    assert payload["errors"][0]["index"] == 1


def test_mcp_validate_tool_rejects_unsafe_urls() -> None:
    response = mcp.handle_request(
        {
            "jsonrpc": "2.0",
            "id": 30,
            "method": "tools/call",
            "params": {
                "name": "validate_jobfiller_export",
                "arguments": {
                    "jobs": [
                        {"url": "http://127.0.0.1:8000/jobs/private", "company": "UnsafeCo"},
                        {
                            "url": "https://example.com/jobs/backend",
                            "apply_url": "file:///tmp/private",
                            "company": "UnsafeApplyCo",
                        },
                    ]
                },
            },
        }
    )

    assert response is not None
    payload = json.loads(response["result"]["content"][0]["text"])
    assert payload["valid"] is False
    assert payload["error_count"] == 2


def test_mcp_validate_tool_matches_backend_field_limits() -> None:
    response = mcp.handle_request(
        {
            "jsonrpc": "2.0",
            "id": 32,
            "method": "tools/call",
            "params": {
                "name": "validate_jobfiller_export",
                "arguments": {
                    "jobs": [
                        {
                            "url": "https://example.com/jobs/company-too-long",
                            "company": "X" * 201,
                            "title": "Backend Engineer",
                        },
                        {
                            "url": "https://example.com/jobs/score-too-high",
                            "company": "ScoreCo",
                            "fit_score": 999,
                        },
                    ]
                },
            },
        }
    )

    assert response is not None
    payload = json.loads(response["result"]["content"][0]["text"])
    assert payload["valid"] is False
    assert payload["valid_count"] == 0
    assert payload["error_count"] == 2
    assert {error["index"] for error in payload["errors"]} == {0, 1}
    assert "company" in payload["errors"][0]["error"].lower()
    assert "fit_score" in payload["errors"][1]["error"].lower()


def test_mcp_export_rejects_remote_api_base() -> None:
    response = mcp.handle_request(
        {
            "jsonrpc": "2.0",
            "id": 4,
            "method": "tools/call",
            "params": {
                "name": "jobfiller_status",
                "arguments": {"api_base": "https://example.com/api"},
            },
        }
    )

    assert response is not None
    assert response["result"]["isError"] is True
    assert "localhost" in response["result"]["content"][0]["text"]


def test_mcp_export_forwards_valid_jobs_to_bulk_import(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[str, str, dict, dict]] = []
    monkeypatch.setenv("JOBFILLER_LOCAL_TOKEN", "test-token")

    def fake_json_request(
        method: str,
        url: str,
        body: dict | None = None,
        timeout: float = 20.0,  # noqa: ARG001
        headers: dict | None = None,
    ) -> dict:
        calls.append((method, url, body or {}, headers or {}))
        return {"imported": 1, "errors": [], "job_ids": [123]}

    monkeypatch.setattr(mcp, "_json_request", fake_json_request)

    response = mcp.handle_request(
        {
            "jsonrpc": "2.0",
            "id": 6,
            "method": "tools/call",
            "params": {
                "name": "export_jobs_to_jobfiller",
                "arguments": {
                    "source": "codex-test",
                    "process": False,
                    "api_base": "http://127.0.0.1:8001/api",
                    "jobs": [{"url": "https://example.com/jobs/backend", "company": "ExampleCo"}],
                },
            },
        }
    )

    assert response is not None
    assert response["result"]["isError"] is False
    assert calls == [
        (
            "POST",
            "http://127.0.0.1:8001/api/imports/bulk",
            {
                "jobs": [{"url": "https://example.com/jobs/backend", "company": "ExampleCo"}],
                "source": "codex-test",
                "process": False,
            },
            {"X-JobFiller-Token": "test-token"},
        )
    ]
    payload = json.loads(response["result"]["content"][0]["text"])
    assert payload["response"]["job_ids"] == [123]


def test_mcp_export_defaults_to_runtime_api_base_and_no_processing(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    runtime = tmp_path / "jobfiller-runtime.json"
    runtime.write_text(json.dumps({"api_base": "http://127.0.0.1:8077/api", "mutation_token": "test-token"}), encoding="utf-8")
    monkeypatch.setenv("JOBFILLER_RUNTIME_CONFIG", str(runtime))
    monkeypatch.delenv("JOBFILLER_API_BASE", raising=False)
    calls: list[tuple[str, str, dict, dict]] = []

    def fake_json_request(
        method: str,
        url: str,
        body: dict | None = None,
        timeout: float = 20.0,  # noqa: ARG001
        headers: dict | None = None,
    ) -> dict:
        calls.append((method, url, body or {}, headers or {}))
        return {"imported": 1, "errors": [], "job_ids": [456]}

    monkeypatch.setattr(mcp, "_json_request", fake_json_request)

    response = mcp.handle_request(
        {
            "jsonrpc": "2.0",
            "id": 31,
            "method": "tools/call",
            "params": {
                "name": "export_jobs_to_jobfiller",
                "arguments": {
                    "source": "runtime-test",
                    "jobs": [{"url": "https://example.com/jobs/backend", "company": "ExampleCo"}],
                },
            },
        }
    )

    assert response is not None
    assert response["result"]["isError"] is False
    assert calls[0][1] == "http://127.0.0.1:8077/api/imports/bulk"
    assert calls[0][2]["process"] is False
    assert calls[0][3]["X-JobFiller-Token"] == "test-token"


def test_mcp_batch_notifications_do_not_emit_responses() -> None:
    raw = mcp.handle_message(
        json.dumps(
            [
                {"jsonrpc": "2.0", "method": "notifications/initialized"},
                {"jsonrpc": "2.0", "id": 5, "method": "ping"},
            ]
        )
    )

    assert raw is not None
    responses = json.loads(raw)
    assert responses == [{"jsonrpc": "2.0", "id": 5, "result": {}}]

from __future__ import annotations

import json
import argparse
import os
import queue
import subprocess
import sys
import threading
import tomllib
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
CLAUDE_CONFIG = ROOT / ".mcp.json"
CODEX_CONFIG = ROOT / ".codex" / "config.toml"
SERVER_PATH = "integrations/mcp/jobfiller_mcp_server.py"
REQUIRED_TOOLS = {"export_jobs_to_jobfiller", "validate_jobfiller_export", "jobfiller_status"}


class McpSmokeError(RuntimeError):
    pass


def validate_configs() -> tuple[str, list[str]]:
    claude_config = json.loads(CLAUDE_CONFIG.read_text(encoding="utf-8"))
    server = claude_config["mcpServers"]["jobfiller"]
    if server.get("type") != "stdio":
        raise McpSmokeError("Claude MCP config must use stdio transport.")
    if server.get("args") != [SERVER_PATH]:
        raise McpSmokeError(f"Claude MCP config must point to {SERVER_PATH}.")

    codex_config = tomllib.loads(CODEX_CONFIG.read_text(encoding="utf-8"))
    codex_server = codex_config["mcp_servers"]["jobfiller"]
    if codex_server.get("args") != [SERVER_PATH]:
        raise McpSmokeError(f"Codex MCP config must point to {SERVER_PATH}.")
    if "export_jobs_to_jobfiller" not in set(codex_server.get("enabled_tools", [])):
        raise McpSmokeError("Codex MCP config must enable export_jobs_to_jobfiller.")

    command = str(server.get("command") or "").strip()
    if not command:
        raise McpSmokeError("Claude MCP config is missing a command.")
    args = [str(item) for item in server.get("args", [])]
    if not (ROOT / SERVER_PATH).exists():
        raise McpSmokeError(f"MCP server file is missing: {SERVER_PATH}")
    return command, args


def start_reader(stream, output: queue.Queue[str]) -> threading.Thread:  # noqa: ANN001
    def read_lines() -> None:
        for line in iter(stream.readline, ""):
            output.put(line)

    thread = threading.Thread(target=read_lines, daemon=True)
    thread.start()
    return thread


def call_rpc(process: subprocess.Popen[str], output: queue.Queue[str], payload: dict[str, Any]) -> dict[str, Any]:
    if not process.stdin:
        raise McpSmokeError("MCP process stdin is unavailable.")
    process.stdin.write(json.dumps(payload, separators=(",", ":")) + "\n")
    process.stdin.flush()
    try:
        raw = output.get(timeout=10)
    except queue.Empty as exc:
        raise McpSmokeError("Timed out waiting for MCP response.") from exc
    try:
        response = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise McpSmokeError(f"MCP returned invalid JSON: {raw!r}") from exc
    if "error" in response:
        raise McpSmokeError(f"MCP returned JSON-RPC error: {response['error']}")
    return response


def smoke_protocol(command: str, args: list[str], *, live_export: bool = False, api_base: str = "") -> None:
    env = os.environ.copy()
    process = subprocess.Popen(
        [command, *args],
        cwd=ROOT,
        env=env,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    assert process.stdout is not None
    stdout_queue: queue.Queue[str] = queue.Queue()
    start_reader(process.stdout, stdout_queue)

    try:
        initialize = call_rpc(
            process,
            stdout_queue,
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2025-03-26",
                    "capabilities": {},
                    "clientInfo": {"name": "jobfiller-smoke", "version": "0.1.0"},
                },
            },
        )
        if initialize["result"]["serverInfo"]["name"] != "jobfiller-mcp":
            raise McpSmokeError("MCP initialize response did not identify jobfiller-mcp.")

        tools_response = call_rpc(process, stdout_queue, {"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
        tools = {tool["name"] for tool in tools_response["result"]["tools"]}
        missing = REQUIRED_TOOLS - tools
        if missing:
            raise McpSmokeError("MCP tool list is missing: " + ", ".join(sorted(missing)))

        validate_response = call_rpc(
            process,
            stdout_queue,
            {
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {
                    "name": "validate_jobfiller_export",
                    "arguments": {
                        "jobs": [
                            {
                                "url": "https://example.com/jobs/mcp-smoke",
                                "company": "Example Systems",
                                "title": "Backend Engineer",
                            }
                        ]
                    },
                },
            },
        )
        payload = json.loads(validate_response["result"]["content"][0]["text"])
        if not payload["valid"] or payload["valid_count"] != 1:
            raise McpSmokeError("MCP validation tool rejected a valid public job URL.")

        if live_export:
            if not api_base:
                raise McpSmokeError("--api-base is required with --live-export.")
            export_response = call_rpc(
                process,
                stdout_queue,
                {
                    "jsonrpc": "2.0",
                    "id": 4,
                    "method": "tools/call",
                    "params": {
                        "name": "export_jobs_to_jobfiller",
                        "arguments": {
                            "source": "mcp-smoke",
                            "process": False,
                            "api_base": api_base,
                            "jobs": [
                                {
                                    "url": "https://example.com/jobs/mcp-live-export-smoke",
                                    "company": "MCP Smoke",
                                    "title": "Backend Engineer",
                                    "location": "Remote",
                                    "work_model": "Remote",
                                    "key_requirements": "APIs; validation; local agents",
                                    "keywords": "MCP; Codex; Claude Code; JobFiller",
                                    "posting_age_text": "1 hour ago",
                                }
                            ],
                        },
                    },
                },
            )
            export_payload = json.loads(export_response["result"]["content"][0]["text"])
            api_response = export_payload.get("response", {})
            if export_response["result"].get("isError") or api_response.get("imported") != 1:
                raise McpSmokeError(f"MCP live export did not import exactly one job: {export_payload}")
    finally:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify JobFiller MCP stdio config and export tools.")
    parser.add_argument("--live-export", action="store_true", help="Call export_jobs_to_jobfiller against a running local API.")
    parser.add_argument("--api-base", default="", help="Local JobFiller API base for --live-export, for example http://127.0.0.1:8001/api.")
    cli_args = parser.parse_args()

    try:
        command, server_args = validate_configs()
        smoke_protocol(command, server_args, live_export=cli_args.live_export, api_base=cli_args.api_base)
    except Exception as exc:  # noqa: BLE001 - smoke output should be direct.
        print(f"FAIL MCP stdio smoke failed: {exc}", flush=True)
        return 1
    suffix = " and live export" if cli_args.live_export else ""
    print(f"OK   MCP stdio smoke passed for Codex/Claude export tools{suffix}.", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

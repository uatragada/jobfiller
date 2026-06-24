from __future__ import annotations

import json
import tomllib
from pathlib import Path


def test_codex_and_claude_project_mcp_configs_point_to_bundled_server() -> None:
    server_path = Path("integrations/mcp/jobfiller_mcp_server.py")
    assert server_path.exists()

    codex_config = tomllib.loads(Path(".codex/config.toml").read_text(encoding="utf-8"))
    codex_server = codex_config["mcp_servers"]["jobfiller"]
    assert codex_server["command"] == "python"
    assert codex_server["args"] == ["integrations/mcp/jobfiller_mcp_server.py"]
    assert "export_jobs_to_jobfiller" in codex_server["enabled_tools"]

    claude_config = json.loads(Path(".mcp.json").read_text(encoding="utf-8"))
    server = claude_config["mcpServers"]["jobfiller"]
    assert server["type"] == "stdio"
    assert server["command"] == "python"
    assert server["args"] == ["integrations/mcp/jobfiller_mcp_server.py"]

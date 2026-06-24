from __future__ import annotations

import json
from pathlib import Path


def test_codex_and_claude_project_mcp_configs_point_to_bundled_server() -> None:
    server_path = Path("integrations/mcp/jobfiller_mcp_server.py")
    assert server_path.exists()

    codex_config = Path(".codex/config.toml").read_text(encoding="utf-8")
    assert "[mcp_servers.jobfiller]" in codex_config
    assert 'command = "python"' in codex_config
    assert 'args = ["integrations/mcp/jobfiller_mcp_server.py"]' in codex_config

    claude_config = json.loads(Path(".mcp.json").read_text(encoding="utf-8"))
    server = claude_config["mcpServers"]["jobfiller"]
    assert server["type"] == "stdio"
    assert server["command"] == "python"
    assert server["args"] == ["integrations/mcp/jobfiller_mcp_server.py"]

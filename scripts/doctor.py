from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def ok(message: str) -> tuple[bool, str]:
    return True, f"OK   {message}"


def warn(message: str) -> tuple[bool, str]:
    return True, f"WARN {message}"


def fail(message: str) -> tuple[bool, str]:
    return False, f"FAIL {message}"


def command_version(command: str, args: list[str]) -> tuple[int, str]:
    try:
        completed = subprocess.run(
            [command, *args],
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return 1, str(exc)
    return completed.returncode, completed.stdout.strip()


def check_python() -> tuple[bool, str]:
    version = sys.version_info
    if version >= (3, 10):
        return ok(f"Python {version.major}.{version.minor}.{version.micro}")
    return fail(f"Python 3.10+ required, found {version.major}.{version.minor}.{version.micro}")


def check_node() -> tuple[bool, str]:
    node = shutil.which("node")
    if not node:
        return fail("Node.js is missing. Install Node.js 20.19+.")
    code, output = command_version(node, ["--version"])
    if code:
        return fail(f"Could not read Node.js version: {output}")
    raw = output.lstrip("v")
    parts = raw.split(".")
    try:
        major, minor = int(parts[0]), int(parts[1])
    except (IndexError, ValueError):
        return fail(f"Could not parse Node.js version: {output}")
    if (major, minor) >= (20, 19):
        return ok(f"Node.js {output}")
    return fail(f"Node.js 20.19+ required, found {output}")


def check_npm_or_pnpm() -> tuple[bool, str]:
    candidates = [("npm", ["--version"]), ("pnpm", ["--version"])]
    found = []
    for command, args in candidates:
        path = shutil.which(command)
        if not path:
            continue
        code, output = command_version(path, args)
        if code == 0:
            found.append(f"{command} {output}")
    if found:
        return ok("Package manager available: " + ", ".join(found))
    return fail("npm or pnpm is required.")


def check_required_files() -> tuple[bool, str]:
    required = [
        "requirements.txt",
        "requirements-dev.txt",
        "requirements-optional.txt",
        "app/frontend/package-lock.json",
        "start_jobfiller.py",
        "Start-JobFiller.ps1",
        "scripts/smoke_mcp.py",
        ".codex/config.toml",
        ".mcp.json",
        "integrations/mcp/jobfiller_mcp_server.py",
        ".env.example",
    ]
    missing = [path for path in required if not (ROOT / path).exists()]
    if missing:
        return fail("Missing required files: " + ", ".join(missing))
    return ok("Required source/config files are present")


def check_json_files() -> tuple[bool, str]:
    for path in [".mcp.json", "examples/jobs.sample.json", "examples/mcp-export.sample.json"]:
        try:
            json.loads((ROOT / path).read_text(encoding="utf-8"))
        except Exception as exc:  # noqa: BLE001 - doctor output should be direct.
            return fail(f"{path} is invalid JSON: {exc}")
    return ok("JSON config and sample files parse")


def check_gitignore_privacy() -> tuple[bool, str]:
    gitignore = (ROOT / ".gitignore").read_text(encoding="utf-8")
    required_patterns = ["outputs/", "artifacts/", ".env", "*.db", "*resume*.pdf", "*cover-letter*.md"]
    missing = [pattern for pattern in required_patterns if pattern not in gitignore]
    if missing:
        return fail(".gitignore missing privacy patterns: " + ", ".join(missing))
    if "!.env.example" not in gitignore:
        return fail(".gitignore must explicitly allow .env.example")
    return ok("Generated/private app data is ignored")


def check_ollama_hint() -> tuple[bool, str]:
    configured = os.environ.get("JOBFILLER_OLLAMA_MODEL", "").strip()
    if configured:
        return ok(f"Ollama model configured: {configured}")
    return warn("No JOBFILLER_OLLAMA_MODEL set; deterministic fallback grading will be used")


def main() -> int:
    checks = [
        check_python,
        check_node,
        check_npm_or_pnpm,
        check_required_files,
        check_json_files,
        check_gitignore_privacy,
        check_ollama_hint,
    ]
    results = [check() for check in checks]
    for _, message in results:
        print(message)
    return 0 if all(success for success, _ in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())

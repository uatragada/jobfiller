from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "app" / "frontend"


def venv_python_path() -> Path:
    if sys.platform.startswith("win"):
        return ROOT / ".venv" / "Scripts" / "python.exe"
    return ROOT / ".venv" / "bin" / "python"


def run_step(label: str, command: list[str], *, cwd: Path = ROOT) -> bool:
    started = time.perf_counter()
    print(f"\n==> {label}", flush=True)
    print(" ".join(command), flush=True)
    completed = subprocess.run(command, cwd=cwd, check=False)
    elapsed = time.perf_counter() - started
    if completed.returncode:
        print(f"FAIL {label} failed after {elapsed:.1f}s", flush=True)
        return False
    print(f"OK   {label} passed in {elapsed:.1f}s", flush=True)
    return True


def ensure_release_python() -> str:
    python = venv_python_path()
    if not python.exists():
        if not run_step("Python virtual environment", [sys.executable, "-m", "venv", str(ROOT / ".venv")]):
            raise SystemExit(1)
    probe = subprocess.run(
        [str(python), "-c", "import fastapi, sqlalchemy, uvicorn, pydantic, pytest, httpx2"],
        cwd=ROOT,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    if probe.returncode:
        if not run_step(
            "Python release dependencies",
            [str(python), "-m", "pip", "install", "-r", str(ROOT / "requirements-dev.txt")],
        ):
            raise SystemExit(1)
    return str(python)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run JobFiller release verification checks.")
    parser.add_argument(
        "--skip-npm-ci",
        action="store_true",
        help="Skip npm ci even when app/frontend/node_modules is missing.",
    )
    args = parser.parse_args()

    npm = shutil.which("npm")
    if not npm:
        print("FAIL npm is required for frontend release verification.", flush=True)
        return 1
    python = ensure_release_python()

    checks: list[tuple[str, list[str], Path]] = [
        ("Python compile", [python, "-m", "py_compile", "start_jobfiller.py", "scripts/doctor.py", "scripts/verify_release.py"], ROOT),
        ("Backend tests", [python, "-m", "pytest", "-q"], ROOT),
        ("Clone doctor", [python, "scripts/doctor.py"], ROOT),
    ]

    if not args.skip_npm_ci and not (FRONTEND / "node_modules").exists():
        checks.append(("Frontend install", [npm, "ci"], FRONTEND))

    checks.extend(
        [
            ("Frontend tests", [npm, "test"], FRONTEND),
            ("Frontend production build", [npm, "run", "build"], FRONTEND),
            ("Startup smoke", [python, "start_jobfiller.py", "--smoke", "--startup-budget", "30"], ROOT),
        ]
    )

    failures = 0
    for label, command, cwd in checks:
        if not run_step(label, command, cwd=cwd):
            failures += 1
            break

    if failures:
        return 1

    print("\nRelease verification passed.", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

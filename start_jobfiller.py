from __future__ import annotations

import json
import os
import shutil
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parent
FRONTEND_DIR = ROOT / "app" / "frontend"
OUTPUTS_DIR = ROOT / "outputs"
LOGS_DIR = ROOT / "artifacts"
BACKEND_LOG = LOGS_DIR / "jobfiller-backend-current.log"
BACKEND_ERR_LOG = LOGS_DIR / "jobfiller-backend-current.err.log"
FRONTEND_LOG = LOGS_DIR / "jobfiller-frontend-current.log"
FRONTEND_ERR_LOG = LOGS_DIR / "jobfiller-frontend-current.err.log"
RUNTIME_CONFIG = OUTPUTS_DIR / "jobfiller-runtime.json"


def env_int(name: str, default: int) -> int:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError as exc:
        raise SystemExit(f"{name} must be an integer, got {raw!r}") from exc


def run(command: list[str], *, cwd: Path = ROOT, env: dict[str, str] | None = None) -> None:
    print("+", " ".join(command))
    completed = subprocess.run(command, cwd=cwd, env=env, check=False)
    if completed.returncode:
        raise SystemExit(f"Command failed with exit code {completed.returncode}: {' '.join(command)}")


def command_path(candidates: list[str]) -> str:
    for candidate in candidates:
        if not candidate:
            continue
        candidate_path = Path(candidate)
        if candidate_path.exists():
            return str(candidate_path)
        resolved = shutil.which(candidate)
        if resolved:
            return resolved
    raise SystemExit(f"Missing executable. Checked: {', '.join(item for item in candidates if item)}")


def venv_python_path() -> Path:
    if os.name == "nt":
        return ROOT / ".venv" / "Scripts" / "python.exe"
    return ROOT / ".venv" / "bin" / "python"


def ensure_python_environment() -> str:
    python = venv_python_path()
    if not python.exists():
        print("Creating local Python virtual environment in .venv...")
        run([sys.executable, "-m", "venv", str(ROOT / ".venv")])
    try:
        subprocess.run(
            [str(python), "-c", "import fastapi, sqlalchemy, uvicorn, pydantic"],
            cwd=ROOT,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=True,
        )
    except subprocess.CalledProcessError:
        print("Installing backend dependencies from requirements.txt...")
        run([str(python), "-m", "pip", "install", "-r", str(ROOT / "requirements.txt")])
    return str(python)


def package_manager() -> str:
    return command_path([os.environ.get("JOBFILLER_NPM", ""), os.environ.get("JOBFILLER_PNPM", ""), "npm", "pnpm"])


def package_manager_name(executable: str) -> str:
    return "pnpm" if "pnpm" in Path(executable).name.lower() else "npm"


def ensure_frontend_dependencies(pm: str) -> None:
    if (FRONTEND_DIR / "node_modules").exists():
        return
    name = package_manager_name(pm)
    print(f"Installing frontend dependencies with {name}...")
    if name == "pnpm" and (FRONTEND_DIR / "pnpm-lock.yaml").exists():
        run([pm, "install", "--frozen-lockfile"], cwd=FRONTEND_DIR)
    elif name == "npm" and (FRONTEND_DIR / "package-lock.json").exists():
        run([pm, "ci"], cwd=FRONTEND_DIR)
    else:
        run([pm, "install"], cwd=FRONTEND_DIR)


def is_port_free(port: int, host: str = "127.0.0.1") -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.2)
        return sock.connect_ex((host, port)) != 0


def find_free_port(start: int, max_port: int, host: str = "127.0.0.1") -> int:
    for port in range(start, max_port + 1):
        if is_port_free(port, host):
            return port
    raise SystemExit(f"No free port found in range {start}-{max_port}.")


def http_json(url: str, headers: dict[str, str] | None = None, timeout: float = 2.0) -> dict[str, object]:
    request = urllib.request.Request(url, headers=headers or {})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def wait_for_backend(port: int, timeout_seconds: float = 20.0) -> str:
    deadline = time.monotonic() + timeout_seconds
    base = f"http://127.0.0.1:{port}/api"
    last_error = ""
    while time.monotonic() < deadline:
        try:
            health = http_json(f"{base}/health")
            session = http_json(f"{base}/session")
            token = str(session.get("mutation_token") or "")
            headers = {"X-JobFiller-Token": token}
            model_health = http_json(f"{base}/model-health", headers=headers)
            if health.get("status") == "ok" and health.get("capabilities", {}).get("token_required_for_local_writes") and model_health.get("provider") and token:
                return token
        except (OSError, urllib.error.URLError, json.JSONDecodeError) as exc:
            last_error = str(exc)
        time.sleep(0.35)
    raise SystemExit(f"Backend did not become ready on {base}. Last error: {last_error}")


def wait_for_frontend(frontend_port: int, backend_port: int, token: str, timeout_seconds: float = 20.0) -> None:
    deadline = time.monotonic() + timeout_seconds
    frontend_url = f"http://127.0.0.1:{frontend_port}"
    jobs_url = f"http://127.0.0.1:{backend_port}/api/jobs?sort=newest&remote_first=true"
    headers = {"X-JobFiller-Token": token}
    last_error = ""
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(frontend_url, timeout=2) as response:
                frontend_ok = response.status == 200
            jobs = http_json(jobs_url, headers=headers)
            if frontend_ok and isinstance(jobs, list):
                return
        except (OSError, urllib.error.URLError, json.JSONDecodeError) as exc:
            last_error = str(exc)
        time.sleep(0.35)
    raise SystemExit(f"Frontend did not become ready on {frontend_url}. Last error: {last_error}")


def start_process(command: list[str], *, cwd: Path, stdout_path: Path, stderr_path: Path, env: dict[str, str] | None = None) -> subprocess.Popen[bytes]:
    stdout_path.parent.mkdir(parents=True, exist_ok=True)
    creationflags = 0
    if os.name == "nt":
        creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    stdout_file = stdout_path.open("w", encoding="utf-8")
    stderr_file = stderr_path.open("w", encoding="utf-8")
    return subprocess.Popen(
        command,
        cwd=cwd,
        env=env,
        stdout=stdout_file,
        stderr=stderr_file,
        creationflags=creationflags,
        start_new_session=os.name != "nt",
    )


def write_runtime_config(backend_port: int, frontend_port: int, token: str) -> None:
    OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "api_base": f"http://127.0.0.1:{backend_port}/api",
        "frontend_url": f"http://127.0.0.1:{frontend_port}",
        "mutation_token": token,
        "updated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    RUNTIME_CONFIG.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def main() -> int:
    started = time.monotonic()
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)

    python = ensure_python_environment()
    pm = package_manager()
    ensure_frontend_dependencies(pm)

    backend_start = env_int("JOBFILLER_BACKEND_PORT", 8001)
    backend_max = env_int("JOBFILLER_BACKEND_PORT_MAX", backend_start + 4)
    frontend_start = env_int("JOBFILLER_FRONTEND_PORT", 5173)
    frontend_max = env_int("JOBFILLER_FRONTEND_PORT_MAX", frontend_start + 4)

    backend_port = find_free_port(backend_start, max(backend_start, backend_max))
    frontend_port = find_free_port(frontend_start, max(frontend_start, frontend_max))
    backend_base = f"http://127.0.0.1:{backend_port}/api"

    print(f"Starting JobFiller backend on {backend_base}")
    backend = start_process(
        [python, "-m", "uvicorn", "app.backend.main:app", "--host", "127.0.0.1", "--port", str(backend_port)],
        cwd=ROOT,
        stdout_path=BACKEND_LOG,
        stderr_path=BACKEND_ERR_LOG,
    )
    token = wait_for_backend(backend_port)
    if backend.poll() is not None:
        raise SystemExit(f"Backend exited early. Check {BACKEND_ERR_LOG}")

    frontend_env = os.environ.copy()
    frontend_env["VITE_API_BASE"] = backend_base
    pm_name = package_manager_name(pm)
    frontend_args = ["dev", "--host", "127.0.0.1", "--port", str(frontend_port)]
    if pm_name == "npm":
        frontend_args = ["run", "dev", "--", "--host", "127.0.0.1", "--port", str(frontend_port)]
    print(f"Starting JobFiller dashboard on http://127.0.0.1:{frontend_port}")
    frontend = start_process(
        [pm, *frontend_args],
        cwd=FRONTEND_DIR,
        stdout_path=FRONTEND_LOG,
        stderr_path=FRONTEND_ERR_LOG,
        env=frontend_env,
    )
    wait_for_frontend(frontend_port, backend_port, token)
    if frontend.poll() is not None:
        raise SystemExit(f"Frontend exited early. Check {FRONTEND_ERR_LOG}")

    write_runtime_config(backend_port, frontend_port, token)
    elapsed = round(time.monotonic() - started, 1)
    print(f"Dashboard: http://127.0.0.1:{frontend_port}")
    print(f"Backend API base: {backend_base}")
    print(f"Runtime config for MCP clients: {RUNTIME_CONFIG}")
    print(f"Backend logs: {BACKEND_LOG}")
    print(f"Frontend logs: {FRONTEND_LOG}")
    print(f"Startup completed in {elapsed}s.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

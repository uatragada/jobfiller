from __future__ import annotations

from pathlib import Path


def test_start_script_restarts_backend_by_default_and_requires_reuse_opt_in() -> None:
    source = Path("Start-JobFiller.ps1").read_text(encoding="utf-8")

    assert "$ReuseExistingBackend = ([string]$env:JOBFILLER_REUSE_BACKEND) -match" in source
    assert "Backend already healthy on port" in source
    assert "Stop-VisibleJobFillerBackends" in source

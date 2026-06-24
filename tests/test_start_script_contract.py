from __future__ import annotations

from pathlib import Path


def test_start_script_restarts_backend_by_default_and_requires_reuse_opt_in() -> None:
    source = Path("Start-JobFiller.ps1").read_text(encoding="utf-8")

    assert "$ReuseExistingBackend = ([string]$env:JOBFILLER_REUSE_BACKEND) -match" in source
    assert "$BackendPortMaxScan = $BackendPortStart + 4" in source
    assert "JOBFILLER_BACKEND_PORT_MAX" in source
    assert "JOBFILLER_FRONTEND_PORT" in source
    assert "JOBFILLER_FRONTEND_PORT_MAX" in source
    assert "JOBFILLER_DEV_FRONTEND" in source
    assert "--strictPort" in source
    assert "Test-StaticDashboardReady" in source
    assert "Get-DashboardAssetPaths" in source
    assert "$FrontendAllowedOrigins" in source
    assert "$env:JOBFILLER_ALLOWED_ORIGINS = $FrontendAllowedOrigins" in source
    assert "Backend already healthy on port" in source
    assert "Stop-VisibleJobFillerBackends" in source

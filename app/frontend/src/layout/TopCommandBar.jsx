import React, { useState } from "react";
import { Play, RefreshCcw01 as RefreshCcw, SearchMd, Settings01 as Settings, Sun } from "@untitledui/icons";
import { Button, IconButton } from "../components/ui";

export function TopCommandBar({ search, onSearch, onScan, importUrl, onImportUrl, onImport, onNavigate, liveStatus, onRefresh, loading }) {
  const [userMenuOpen, setUserMenuOpen] = useState(false);
  const isLive = liveStatus?.source === "live";
  const isLoading = liveStatus?.source === "loading";
  const systemTone = isLive ? "green" : isLoading ? "blue" : "amber";
  const systemText = isLive ? "Live" : isLoading ? "Connecting" : "Fixtures";
  const trimmedImportUrl = String(importUrl || "").trim();
  const importUrlInvalid = Boolean(trimmedImportUrl) && !/^https?:\/\/\S+\.\S+/.test(trimmedImportUrl);
  return (
    <header className="topCommandBar">
      <label className="globalSearch">
        <SearchMd size={17} />
        <input value={search || ""} onChange={(event) => onSearch(event.target.value)} placeholder="Search jobs, companies, roles..." />
        <kbd>Ctrl K</kbd>
      </label>
      <Button variant="primary" icon={Play} onClick={onScan} loading={loading === "scan-now"} data-testid="scan-now">Scan Now</Button>
      <label className="importUrl">
        <input value={importUrl || ""} onChange={(event) => onImportUrl(event.target.value)} placeholder="Import URL..." data-testid="import-url-input" />
        <Button size="sm" onClick={onImport} disabled={!trimmedImportUrl || importUrlInvalid} data-testid="import-url-button">Import</Button>
      </label>
      <div className="statusPills">
        <button onClick={onRefresh} title={liveStatus?.label || "Refresh backend data"}><i className={systemTone} />Data <b>{systemText}</b></button>
        <button data-testid="health-pill-scanner" onClick={() => onNavigate("runs-logs")}><i className="blue" />Finder <b>Idle</b></button>
        <button data-testid="health-pill-worker" onClick={() => onNavigate("generate-queue")}><i className={isLive ? "green" : "amber"} />Worker <b>{isLive ? "Synced" : "Fallback"}</b></button>
        <button data-testid="health-pill-llm" onClick={() => onNavigate("model-health")}><i className={isLive ? "green" : "amber"} />Local LLM: <b>{isLive ? "Synced" : "Fallback"}</b></button>
      </div>
      <IconButton label="Refresh live data" icon={RefreshCcw} onClick={onRefresh} loading={loading === "refresh-data"} />
      <IconButton label="Open settings" icon={Settings} onClick={() => onNavigate("settings")} data-testid="command-open-settings" />
      <div className="topUserMenu">
        <IconButton label="User menu" icon={Sun} onClick={() => setUserMenuOpen((open) => !open)} data-testid="top-user-menu" />
        {userMenuOpen && (
          <div className="topUserPopover">
            <strong>Remote-first mode</strong>
            <button data-testid="top-user-settings" onClick={() => { setUserMenuOpen(false); onNavigate("settings"); }}>Settings</button>
          </div>
        )}
      </div>
    </header>
  );
}

import React, { useState } from "react";
import { primaryRoutes } from "../router/routes.jsx";
import { SidebarNav } from "./SidebarNav.jsx";
import { TopCommandBar } from "./TopCommandBar.jsx";
import { ToastProvider, ConfirmDialog } from "../components/ui";

export function AppShell({
  activeRoute,
  onNavigate,
  counts,
  settings,
  topSearch,
  onTopSearch,
  importUrl,
  onImportUrl,
  onImport,
  onScan,
  liveStatus,
  onRefresh,
  loading,
  children,
  toasts,
  dismissToast,
  modal,
  closeModal,
  confirmModal,
}) {
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);

  return (
    <div className={`appShell ${sidebarCollapsed ? "sidebarCollapsed" : ""}`}>
      <SidebarNav
        activeRoute={activeRoute}
        onNavigate={onNavigate}
        counts={counts}
        settings={settings}
        collapsed={sidebarCollapsed}
        onToggleCollapsed={() => setSidebarCollapsed((value) => !value)}
      />
      <div className="appMain">
        <TopCommandBar
          search={topSearch}
          onSearch={onTopSearch}
          onScan={onScan}
          importUrl={importUrl}
          onImportUrl={onImportUrl}
          onImport={onImport}
          onNavigate={onNavigate}
          liveStatus={liveStatus}
          onRefresh={onRefresh}
          loading={loading}
        />
        <nav className="mobileRouteRail" aria-label="Mobile navigation">
          {primaryRoutes.map((route) => {
            const Icon = route.icon;
            return (
              <button key={route.id} className={activeRoute === route.id ? "active" : ""} onClick={() => onNavigate(route.id)}>
                <Icon size={16} />
                {route.label}
              </button>
            );
          })}
        </nav>
        {children}
      </div>
      <ToastProvider toasts={toasts} onDismiss={dismissToast} />
      <ConfirmDialog modal={modal} onClose={closeModal} onConfirm={confirmModal} />
    </div>
  );
}

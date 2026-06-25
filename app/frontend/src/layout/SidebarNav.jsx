import React from "react";
import { ChevronLeft, ChevronRight } from "@untitledui/icons";
import { primaryRoutes } from "../router/routes.jsx";
import { EntityAvatar, IconButton } from "../components/ui";

const navTestIds = {
  "apply-queue": "nav-tomorrow",
  "profile-facts": "nav-facts",
  "runs-logs": "nav-runs",
  "generate-queue": "nav-reprocess",
  "assist-upload": "nav-assist",
  "agent-import-mcp": "nav-agent",
  "export-workbook": "nav-export",
  "model-health": "nav-health",
};

export function SidebarNav({ activeRoute, onNavigate, settings, collapsed = false, onToggleCollapsed }) {
  const CollapseIcon = collapsed ? ChevronRight : ChevronLeft;
  return (
    <aside className={`sidebarNav ${collapsed ? "collapsed" : ""}`}>
      <div className="brandRow">
        <span className="brandMark">JF</span>
        <strong>JobFiller</strong>
        <IconButton
          label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
          icon={CollapseIcon}
          aria-pressed={collapsed}
          onClick={onToggleCollapsed}
        />
      </div>
      <nav aria-label="Primary navigation">
        {primaryRoutes.map((route) => {
          const Icon = route.icon;
          return (
            <button
              key={route.id}
              data-testid={navTestIds[route.id] || `nav-${route.id}`}
              className={activeRoute === route.id ? "active" : ""}
              aria-current={activeRoute === route.id ? "page" : undefined}
              onClick={() => onNavigate(route.id)}
            >
              <Icon size={17} />
              <span>{route.label}</span>
            </button>
          );
        })}
      </nav>
      <footer className="sidebarUser">
        <EntityAvatar name={settings.accountName} />
        <div>
          <strong>{settings.accountName}</strong>
          <span>Admin</span>
        </div>
      </footer>
    </aside>
  );
}

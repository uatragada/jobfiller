import React from "react";
import {
  ArrowDown,
  Check,
  CheckCircle,
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  DotsHorizontal,
  File02 as FileText,
  SearchMd,
  Sliders04 as Sliders,
  X,
} from "@untitledui/icons";

export function Button({ children, variant = "secondary", size = "md", icon: Icon, className = "", loading = false, disabled = false, ...props }) {
  return (
    <button {...props} className={`uiButton ${variant} ${size} ${className}`} disabled={disabled || loading}>
      {Icon && !loading && <Icon size={16} />}
      {loading && <span className="loadingDot" aria-hidden="true" />}
      {children}
    </button>
  );
}

export function IconButton({ label, icon: Icon = DotsHorizontal, className = "", loading = false, disabled = false, ...props }) {
  return (
    <button {...props} className={`iconButton ${className}`} aria-label={label} title={label} disabled={disabled || loading}>
      {loading ? <span className="loadingDot" aria-hidden="true" /> : <Icon size={17} />}
    </button>
  );
}

export function PageHeader({ icon: Icon, title, count, subtitle, children }) {
  return (
    <header className="pageHeader">
      <div className="pageHeaderTitle">
        {Icon && <span className="pageHeaderIcon"><Icon size={22} /></span>}
        <div>
          <div className="pageTitleLine">
            <h1>{title}</h1>
            {count != null && <span className="countPill">{count}</span>}
          </div>
          {subtitle && <p>{subtitle}</p>}
        </div>
      </div>
      {children && <div className="pageHeaderActions">{children}</div>}
    </header>
  );
}

export function MetricCard({ label, value, icon: Icon, tone = "neutral", helper }) {
  return (
    <div className={`metricCard ${tone}`}>
      <div>
        <span>{label}</span>
        <strong>{value}</strong>
        {helper && <small>{helper}</small>}
      </div>
      {Icon && <Icon size={18} />}
    </div>
  );
}

export function NoticeCard({ icon: Icon = FileText, title, message, actionLabel = "Review", count, onAction }) {
  return (
    <section className="noticeCard">
      <span className="noticeIcon"><Icon size={18} /></span>
      <div>
        <strong>{title}</strong>
        <p>{message}</p>
      </div>
      <div className="noticeActions">
        <Button size="sm" onClick={onAction}>{actionLabel}</Button>
        {count != null && <span className="tinyCount">{count}</span>}
      </div>
    </section>
  );
}

function testIdKey(value) {
  return String(value || "").replace(/([a-z0-9])([A-Z])/g, "$1-$2").toLowerCase();
}

export function FilterBar({ search, onSearch, filters = [], onReset, moreLabel = "More filters", onMore, moreActive = false, moreCount = 0, testIdPrefix }) {
  const moreText = moreCount > 0 ? `${moreLabel} (${moreCount})` : moreLabel;
  return (
    <div className="appFilterBar">
      <label className="searchField">
        <SearchMd size={16} />
        <input value={search || ""} onChange={(event) => onSearch?.(event.target.value)} placeholder="Search..." aria-label="Search" data-testid={testIdPrefix ? `${testIdPrefix}-search` : undefined} />
      </label>
      {filters.map((filter) => (
        <label className="selectField" key={filter.key}>
          <select value={filter.value || "all"} onChange={(event) => filter.onChange(event.target.value)} aria-label={filter.label} data-testid={filter.testId || (testIdPrefix ? `${testIdPrefix}-filter-${testIdKey(filter.key)}` : undefined)}>
            {(filter.options || ["all"]).map((option) => {
              const value = typeof option === "string" ? option : option.value;
              const label = typeof option === "string" ? (option === "all" ? filter.label : option) : option.label;
              return <option key={value} value={value}>{label}</option>;
            })}
          </select>
          <ChevronDown size={14} />
        </label>
      ))}
      {onMore && <Button size="sm" variant={moreActive ? "primary" : "ghost"} icon={Sliders} onClick={onMore} aria-pressed={moreActive} data-testid={testIdPrefix ? `${testIdPrefix}-advanced-toggle` : undefined}>{moreText}</Button>}
      <Button size="sm" variant="ghost" onClick={onReset}>Reset</Button>
    </div>
  );
}

export function StatusBadge({ status }) {
  const normalized = String(status || "Unknown").toLowerCase().replace(/[^a-z0-9]+/g, "-");
  return <span className={`statusBadge ${normalized}`}><i />{status || "Unknown"}</span>;
}

export function GradeBadge({ grade }) {
  const normalized = String(grade || "-").toLowerCase().replace(/[^a-z0-9]+/g, "-") || "empty";
  return <span className={`gradeBadge ${normalized}`}>{grade || "-"}</span>;
}

export function ReadyIndicator({ ready, value }) {
  return (
    <span className={`readyIndicator ${ready ? "ready" : "notReady"}`}>
      {ready ? <Check size={14} /> : <X size={14} />}
      {value != null ? `${value}%` : ready ? "Ready" : "Not ready"}
    </span>
  );
}

const KNOWN_COMPANY_DOMAINS = {
  anthropic: "anthropic.com",
  datadog: "datadoghq.com",
  figma: "figma.com",
  linear: "linear.app",
  notion: "notion.so",
  openai: "openai.com",
  stripe: "stripe.com",
  vercel: "vercel.com",
};

const JOB_BOARD_OR_ATS_DOMAINS = new Set([
  "ashbyhq.com",
  "bamboohr.com",
  "greenhouse.io",
  "icims.com",
  "indeed.com",
  "jobvite.com",
  "lever.co",
  "linkedin.com",
  "smartrecruiters.com",
  "workable.com",
  "workdayjobs.com",
]);

function companyKey(value) {
  return String(value || "")
    .toLowerCase()
    .replace(/&/g, "and")
    .replace(/[^a-z0-9]+/g, "")
    .trim();
}

function hostnameFromUrl(value) {
  try {
    return new URL(value).hostname.replace(/^www\./, "").toLowerCase();
  } catch {
    return "";
  }
}

function isJobBoardDomain(hostname) {
  if (hostname.includes("workdayjobs.com")) return true;
  return Array.from(JOB_BOARD_OR_ATS_DOMAINS).some((domain) => hostname === domain || hostname.endsWith(`.${domain}`));
}

export function companyLogoUrl(name, sourceUrl = "") {
  const knownDomain = KNOWN_COMPANY_DOMAINS[companyKey(name)];
  const domain = knownDomain || hostnameFromUrl(sourceUrl);
  if (!domain || isJobBoardDomain(domain)) return "";
  return `https://www.google.com/s2/favicons?domain=${encodeURIComponent(domain)}&sz=64`;
}

export function EntityAvatar({ name, tone = "blue", logoUrl = "" }) {
  const [logoFailed, setLogoFailed] = React.useState(false);
  React.useEffect(() => {
    setLogoFailed(false);
  }, [logoUrl]);
  const initials = String(name || "?").match(/[A-Za-z0-9]+/g)?.slice(0, 2).map((word) => word[0]).join("").toUpperCase() || "?";
  const showLogo = Boolean(logoUrl) && !logoFailed;
  return (
    <span className={`entityAvatar ${tone} ${showLogo ? "hasLogo" : ""}`}>
      {showLogo ? (
        <img src={logoUrl} alt="" loading="lazy" referrerPolicy="no-referrer" onError={() => setLogoFailed(true)} />
      ) : (
        initials
      )}
    </span>
  );
}

export function DataTable({ columns, rows, selectedId, onSelect, sortKey, sortDirection, onSort, getRowId = (row) => row.id, emptyMessage = "No rows match this view.", minWidth, label = "Data table", rowTestIdPrefix, rowTestIdFor }) {
  const gridStyle = {
    "--columns": columns.map((column) => column.width || "minmax(120px,1fr)").join(" "),
    "--table-min-width": minWidth,
  };
  return (
    <div className={`dataTable ${rows.length ? "" : "empty"}`} role="table" aria-label={label}>
      <div className="dataTableScroller">
        <div className="dataTableGrid header" role="row" style={gridStyle}>
          {columns.map((column) => (
            <div role="columnheader" key={column.key}>
              {column.sortable ? (
                <button className={`sortButton ${sortKey === column.key ? "active" : ""}`} onClick={() => onSort?.(column.key)} data-testid={column.testId}>
                  {column.label}
                  <ArrowDown size={13} className={sortKey === column.key && sortDirection === "asc" ? "asc" : ""} />
                </button>
              ) : (
                column.label
              )}
            </div>
          ))}
        </div>
        <div role="rowgroup">
          {rows.map((row) => {
            const id = getRowId(row);
            const isSelected = String(selectedId ?? "") === String(id);
            return (
              <button
                type="button"
                key={id}
                data-testid={`row-${id}`}
                className={`dataTableGrid row jobLine ${isSelected ? "selected" : ""}`}
                style={gridStyle}
                onClick={() => onSelect?.(id)}
                role="row"
                aria-selected={isSelected}
              >
                {columns.map((column, index) => (
                  <span role="cell" data-label={column.label} key={column.key} data-testid={index === 0 ? (rowTestIdFor ? rowTestIdFor(row, id) : rowTestIdPrefix ? `${rowTestIdPrefix}-row-select-${id}` : undefined) : undefined}>
                    {column.render ? column.render(row) : row[column.key]}
                  </span>
                ))}
              </button>
            );
          })}
        </div>
      </div>
      {!rows.length && <EmptyState title="Nothing here yet" message={emptyMessage} />}
    </div>
  );
}

export function PaginationFooter({ page, maxPage, total, pageSize, onPage, displayTotal = total, testIdPrefix, onPageSize, pageSizeOptions }) {
  const start = total ? (page - 1) * pageSize + 1 : 0;
  const end = Math.min(page * pageSize, total);
  return (
    <footer className="paginationFooter">
      <IconButton label="Previous page" icon={ChevronLeft} disabled={page <= 1} onClick={() => onPage(Math.max(1, page - 1))} data-testid={testIdPrefix ? `${testIdPrefix}-page-prev` : undefined} />
      <div className="pageButtons">
        {Array.from({ length: Math.min(maxPage, 5) }, (_, index) => index + 1).map((value) => (
          <button key={value} className={value === page ? "active" : ""} onClick={() => onPage(value)}>{value}</button>
        ))}
      </div>
      <IconButton label="Next page" icon={ChevronRight} disabled={page >= maxPage} onClick={() => onPage(Math.min(maxPage, page + 1))} data-testid={testIdPrefix ? `${testIdPrefix}-page-next` : undefined} />
      <span>{start}-{end} of {displayTotal}</span>
      {onPageSize && (
        <select value={pageSize} onChange={(event) => onPageSize(Number(event.target.value))} aria-label="Page size" data-testid={testIdPrefix ? `${testIdPrefix}-page-size` : undefined}>
          {(pageSizeOptions || [8, 10, 20]).map((value) => <option key={value} value={value}>{value}</option>)}
        </select>
      )}
    </footer>
  );
}

export function InspectorPanel({ title, subtitle, avatar, meta, tabs, activeTab, onTab, children, actions }) {
  const [closed, setClosed] = React.useState(false);
  if (closed) {
    return <aside className="board detailClosed"><Button size="sm" onClick={() => setClosed(false)}>Open details</Button></aside>;
  }
  return (
    <aside className="inspectorPanel">
      <div className="inspectorHeader">
        <div className="inspectorEntity">
          {avatar}
          <div>
            <h2>{title}</h2>
            {subtitle && <p>{subtitle}</p>}
          </div>
        </div>
        <IconButton label="Close inspector" data-testid="inspector-close" icon={X} onClick={() => setClosed(true)} />
        {meta && <div className="inspectorMeta">{meta}</div>}
      </div>
      {tabs && <InspectorTabs tabs={tabs} activeTab={activeTab} onTab={onTab} label="Job detail tabs" />}
      <div className="inspectorBody">{children}</div>
      {actions && <ActionBar>{actions}</ActionBar>}
    </aside>
  );
}

export function InspectorTabs({ tabs, activeTab, onTab, label = "Detail tabs" }) {
  const tabTestIds = {
    Artifacts: "inspector-tab-artifacts",
    "Local LLM Grade": "inspector-tab-grade",
    Questions: "inspector-tab-questions",
    Notes: "inspector-tab-notes",
  };
  return (
    <div className="inspectorTabs" role="tablist" aria-label={label}>
      {tabs.map((tab) => (
        <button key={tab} role="tab" aria-selected={activeTab === tab} className={activeTab === tab ? "active" : ""} onClick={() => onTab(tab)} data-testid={tabTestIds[tab]}>
          {tab}
        </button>
      ))}
    </div>
  );
}

export function ArtifactCard({ title, subtitle, meta, icon: Icon = FileText, onView }) {
  return (
    <div className="artifactCard">
      <span><Icon size={17} /></span>
      <div>
        <strong>{title}</strong>
        {subtitle && <p>{subtitle}</p>}
        {meta && <small>{meta}</small>}
      </div>
      <Button size="sm" onClick={onView}>View</Button>
    </div>
  );
}

export function ActionBar({ children }) {
  return <div className="actionBar">{children}</div>;
}

export function EmptyState({ title = "No data", message = "Try changing filters or adding a new record." }) {
  return (
    <div className="emptyState">
      <CheckCircle size={24} />
      <strong>{title}</strong>
      <p>{message}</p>
    </div>
  );
}

export function LoadingSkeleton() {
  return (
    <div className="loadingSkeleton" aria-busy="true">
      <span />
      <span />
      <span />
    </div>
  );
}

export function ToastProvider({ toasts, onDismiss }) {
  return (
    <div className="toastStack" aria-live="polite">
      {toasts.map((toast) => (
        <button key={toast.id} className={`toast ${toast.tone}`} onClick={() => onDismiss?.(toast.id)}>
          {toast.message}
        </button>
      ))}
    </div>
  );
}

export function ConfirmDialog({ modal, onClose, onConfirm }) {
  if (!modal) return null;
  return (
    <div className="dialogBackdrop">
      <div className="confirmDialog" role="dialog" aria-modal="true" aria-label={modal.title || "Confirm action"}>
        <h2>{modal.title || "Confirm action"}</h2>
        <p>{modal.message}</p>
        <div>
          <Button onClick={onClose} data-testid="report-modal-close">Cancel</Button>
          <Button variant="primary" onClick={() => { onConfirm?.(modal); onClose?.(); }}>Confirm</Button>
        </div>
      </div>
    </div>
  );
}

export function SlideoutDrawer({ open, children }) {
  return <div className={`slideoutDrawer ${open ? "open" : ""}`}>{children}</div>;
}

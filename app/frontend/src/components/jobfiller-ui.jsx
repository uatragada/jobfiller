import React from "react";
import { SearchMd } from "@untitledui/icons";
import { FilterBar } from "@/components/untitled-ui/application/filter-bar/filter-bar";
import { Dialog, Modal, ModalOverlay } from "@/components/untitled-ui/application/modals/modal";
import { NavItemBase } from "@/components/untitled-ui/application/app-navigation/base-components/nav-item";
import { Tabs as UntitledTabs } from "@/components/untitled-ui/application/tabs/tabs";
import { Avatar } from "@/components/untitled-ui/base/avatar/avatar";
import { Badge, BadgeWithDot } from "@/components/untitled-ui/base/badges/badges";
import { Button as UntitledButton } from "@/components/untitled-ui/base/buttons/button";
import { Checkbox } from "@/components/untitled-ui/base/checkbox/checkbox";
import { InputBase } from "@/components/untitled-ui/base/input/input";
import { Select } from "@/components/untitled-ui/base/select/select";
import { Toggle } from "@/components/untitled-ui/base/toggle/toggle";
import { cx } from "@/utils/cx";

export function statusClass(status) {
  return `status ${String(status || "").toLowerCase().replace(/_/g, "-")}`;
}

function statusColor(status) {
  const value = String(status || "").toLowerCase();
  if (value.includes("rejected") || value.includes("failed") || value.includes("error")) return "error";
  if (value.includes("action") || value.includes("interview") || value.includes("needs") || value.includes("qa") || value.includes("warning")) return "warning";
  if (value.includes("ready") || value.includes("succeeded") || value.includes("done")) return "success";
  if (value.includes("running") || value.includes("parsed") || value.includes("generating")) return "blue";
  if (value.includes("applied")) return "blue";
  return "brand";
}

export function UButton({ variant = "secondary", disabled = false, loading = false, onClick, children, ...props }) {
  return (
    <UntitledButton
      {...props}
      color={variant === "primary" ? "primary" : variant === "tertiary" ? "tertiary" : "secondary"}
      size={props.size || "xs"}
      isDisabled={disabled}
      isLoading={loading}
      onPress={onClick}
    >
      {children}
    </UntitledButton>
  );
}

export function IconButton({ label, title, icon: Icon, children, disabled = false, onClick, className = "", ...props }) {
  return (
    <UButton
      {...props}
      aria-label={label}
      title={title || label}
      className={cx("plainIcon jfIconButton", className)}
      disabled={disabled}
      onClick={onClick}
      iconLeading={Icon}
      size={props.size || "sm"}
    >
      {children}
    </UButton>
  );
}

export function StatusBadge({ status }) {
  return (
    <BadgeWithDot type="pill-color" size="sm" color={statusColor(status)} className={statusClass(status)}>
      {status}
    </BadgeWithDot>
  );
}

export function CountBadge({ children, tone = "brand" }) {
  return (
    <Badge type="pill-color" size="sm" color={tone} className={`countBadge ${tone}`}>
      {children}
    </Badge>
  );
}

export function UserAvatar({ name, size = "sm", className = "" }) {
  const initial = String(name || "J").trim().slice(0, 1).toUpperCase() || "J";
  return <Avatar size={size} initials={initial} className={className} contentClassName="jfAvatarContent" />;
}

export function AppNavItem({ testId, current, icon, label, badge, badgeTone = "brand", onClick }) {
  return (
    <NavItemBase
      type="link"
      href="#"
      current={current}
      icon={icon}
      badge={badge != null ? <CountBadge tone={badgeTone}>{badge}</CountBadge> : null}
      testId={testId}
      onClick={(event) => {
        event.preventDefault();
        onClick?.(event);
      }}
    >
      {label}
    </NavItemBase>
  );
}

export function TextInput({ testId, className = "", icon, ...props }) {
  return (
    <InputBase
      {...props}
      data-testid={testId}
      size="sm"
      icon={icon}
      wrapperClassName={cx("jfTextInput", className)}
      inputClassName="jfTextInputNative"
    />
  );
}

export function SearchInput(props) {
  return <TextInput icon={SearchMd} {...props} />;
}

export function TextArea({ testId, className = "", ...props }) {
  return <textarea {...props} data-testid={testId} className={cx("jfTextarea", className)} />;
}

export function AppCheckbox({ testId, checked, onChange, label, ariaLabel, className = "", ...props }) {
  const accessibleLabel = ariaLabel || props["aria-label"] || (typeof label === "string" ? label : undefined);
  return (
    <Checkbox
      {...props}
      data-testid={testId}
      aria-label={accessibleLabel}
      isSelected={checked}
      onChange={onChange}
      label={label}
      className={cx("jfCheckbox", className)}
    />
  );
}

export function AppToggle({ testId, checked, onChange, label, hint, className = "" }) {
  return <Toggle data-testid={testId} isSelected={checked} onChange={onChange} label={label} hint={hint} className={cx("jfToggle", className)} />;
}

export function AppSelect({ testId, value, onChange, options, placeholder = "Select", className = "", ariaLabel }) {
  const items = options.map((option) => (typeof option === "string" ? { value: option, label: option } : option));
  return (
    <Select
      data-testid={testId}
      data-value={String(value ?? "")}
      aria-label={ariaLabel}
      selectedKey={String(value ?? "")}
      onSelectionChange={(key) => onChange(String(key))}
      items={items.map((item) => ({ id: String(item.value), label: item.label, supportingText: item.supportingText }))}
      size="sm"
      placeholder={placeholder}
      className={cx("jfSelect", className)}
      popoverClassName="jfSelectPopover"
    >
      {(item) => (
        <Select.Item key={item.id} id={item.id} data-testid={`${testId}-option-${item.id}`} label={item.label}>
          {item.label}
        </Select.Item>
      )}
    </Select>
  );
}

export function AppTabs({ label, selectedKey, onSelectionChange, tabs, className = "" }) {
  return (
    <UntitledTabs selectedKey={selectedKey} onSelectionChange={(key) => onSelectionChange(String(key))} className={cx("jfTabs", className)}>
      <UntitledTabs.List aria-label={label} type="button-minimal" size="sm">
        {tabs.map((tab) => (
          <UntitledTabs.Item key={tab.key} id={tab.key} data-testid={tab.testId} badge={tab.badge}>
            {tab.label}
          </UntitledTabs.Item>
        ))}
      </UntitledTabs.List>
    </UntitledTabs>
  );
}

export function AppModal({ children, className = "", isOpen = true, onClose, label = "JobFiller dialog" }) {
  return (
    <ModalOverlay isOpen={isOpen} onOpenChange={(open) => { if (!open) onClose?.(); }} isDismissable>
      <Modal className={cx("modal", className)}>
        <Dialog aria-label={label}>{children}</Dialog>
      </Modal>
    </ModalOverlay>
  );
}

export function FilterShell({ children, actions, className = "" }) {
  return (
    <FilterBar.Root className={cx("filterBar", className)}>
      <FilterBar.Content>{children}</FilterBar.Content>
      {actions && <FilterBar.Actions>{actions}</FilterBar.Actions>}
    </FilterBar.Root>
  );
}

export function SurfaceCard({ as: Element = "div", className = "", children, ...props }) {
  return (
    <Element {...props} className={cx("infoCard", className)}>
      {children}
    </Element>
  );
}

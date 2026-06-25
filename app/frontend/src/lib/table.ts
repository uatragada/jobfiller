export function textIncludes(value: unknown, query: string) {
  return String(value ?? "").toLowerCase().includes(query.toLowerCase());
}

export function applySearch<T extends Record<string, unknown>>(rows: T[], query: string, fields: (keyof T | ((row: T) => unknown))[]) {
  const normalized = query.trim().toLowerCase();
  if (!normalized) return rows;
  return rows.filter((row) =>
    fields.some((field) => {
      const value = typeof field === "function" ? field(row) : row[field];
      return textIncludes(value, normalized);
    }),
  );
}

export function applySelectFilters<T extends Record<string, unknown>>(rows: T[], filters: Record<string, string>, aliases: Record<string, keyof T | ((row: T) => unknown)>) {
  return rows.filter((row) =>
    Object.entries(filters).every(([key, filterValue]) => {
      if (!filterValue || filterValue === "all") return true;
      const accessor = aliases[key];
      const value = typeof accessor === "function" ? accessor(row) : row[accessor];
      return String(value ?? "") === filterValue;
    }),
  );
}

export function sortRows<T extends Record<string, unknown>>(rows: T[], sortKey: string, direction: "asc" | "desc" = "asc", accessors: Record<string, keyof T | ((row: T) => unknown)> = {}) {
  if (!sortKey) return rows;
  const accessor = accessors[sortKey] || sortKey;
  const multiplier = direction === "desc" ? -1 : 1;
  return [...rows].sort((a, b) => {
    const av = typeof accessor === "function" ? accessor(a) : a[accessor as keyof T];
    const bv = typeof accessor === "function" ? accessor(b) : b[accessor as keyof T];
    const an = Number(av);
    const bn = Number(bv);
    if (Number.isFinite(an) && Number.isFinite(bn)) return (an - bn) * multiplier;
    return String(av ?? "").localeCompare(String(bv ?? ""), undefined, { numeric: true, sensitivity: "base" }) * multiplier;
  });
}

export function paginateRows<T>(rows: T[], page: number, pageSize: number) {
  const maxPage = Math.max(1, Math.ceil(rows.length / pageSize));
  const safePage = Math.min(Math.max(1, page), maxPage);
  return {
    page: safePage,
    maxPage,
    total: rows.length,
    rows: rows.slice((safePage - 1) * pageSize, safePage * pageSize),
  };
}

export function uniqueOptions<T extends Record<string, unknown>>(rows: T[], key: keyof T) {
  return ["all", ...Array.from(new Set(rows.map((row) => String(row[key] ?? "")).filter(Boolean))).sort()];
}

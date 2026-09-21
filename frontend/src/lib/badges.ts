const CATEGORY_BADGE: Record<string, string> = {
  major: "badge-red",
  minor: "badge-amber",
  technical: "badge-sky",
  administrative: "badge-slate",
  unreported: "badge-violet",
};

export const CATEGORY_COLOR: Record<string, string> = {
  major: "#ef4444",
  minor: "#f59e0b",
  technical: "#0ea5e9",
  administrative: "#94a3b8",
  unreported: "#8b5cf6",
};

export const CATEGORY_BAR_CLASS: Record<string, string> = {
  major: "bg-red-500",
  minor: "bg-amber-500",
  technical: "bg-sky-500",
  administrative: "bg-slate-400",
  unreported: "bg-violet-500",
};

export function categoryBadgeClass(category: string | null): string {
  if (!category) return "badge badge-slate";
  return `badge ${CATEGORY_BADGE[category] ?? "badge-slate"}`;
}

const STATUS_BADGE: Record<string, string> = {
  queued: "badge-amber",
  approved: "badge-green",
  rejected: "badge-red",
};

export function statusBadgeClass(status: string): string {
  return `badge ${STATUS_BADGE[status] ?? "badge-slate"}`;
}

const CATEGORY_BADGE: Record<string, string> = {
  major: "badge-red",
  minor: "badge-amber",
  technical: "badge-sky",
  administrative: "badge-slate",
  unreported: "badge-violet",
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

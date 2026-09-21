import type { TriageResult } from "../types";

export const CATEGORIES = ["major", "minor", "technical", "administrative", "unreported"];

export function needsCapa(r: TriageResult): boolean {
  const actions = r.memo?.recommended_capa_actions ?? [];
  if (actions.length === 0) return false;
  const status = r.capa_actions_status ?? [];
  return !actions.every((_, i) => status[i] === true);
}

export function isOpenReport(r: TriageResult): boolean {
  return r.status !== "approved" && r.status !== "rejected";
}

export function attentionLevel(majorCount: number): { label: string; className: string } {
  if (majorCount >= 3) return { label: "High", className: "badge badge-red" };
  if (majorCount >= 1) return { label: "Medium", className: "badge badge-amber" };
  return { label: "Low", className: "badge badge-slate" };
}

function monthLabel(date: Date): string {
  return date.toLocaleDateString(undefined, { month: "short" });
}

export function monthlyTrend(
  reports: TriageResult[],
  months: number,
): { key: string; label: string; count: number }[] {
  const now = new Date();
  const buckets: { key: string; label: string; count: number }[] = [];
  for (let i = months - 1; i >= 0; i--) {
    const d = new Date(now.getFullYear(), now.getMonth() - i, 1);
    buckets.push({ key: `${d.getFullYear()}-${d.getMonth()}`, label: monthLabel(d), count: 0 });
  }
  const byKey = new Map(buckets.map((b) => [b.key, b]));
  for (const r of reports) {
    const d = new Date(r.created_at);
    if (Number.isNaN(d.getTime())) continue;
    const key = `${d.getFullYear()}-${d.getMonth()}`;
    const bucket = byKey.get(key);
    if (bucket) bucket.count += 1;
  }
  return buckets;
}

export function categoryBreakdown(reports: TriageResult[]): { category: string; count: number }[] {
  const counts = new Map<string, number>();
  for (const r of reports) {
    const cat = r.category ?? "unreported";
    counts.set(cat, (counts.get(cat) ?? 0) + 1);
  }
  return CATEGORIES.map((cat) => ({ category: cat, count: counts.get(cat) ?? 0 })).filter(
    (c) => c.count > 0,
  );
}

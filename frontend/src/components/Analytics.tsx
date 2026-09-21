import { useEffect, useMemo, useState } from "react";
import { AlertTriangle, CheckCircle2, ClipboardList, Gauge } from "lucide-react";
import { listReports } from "../api";
import type { TriageResult } from "../types";
import { CATEGORY_BAR_CLASS } from "../lib/badges";
import { BarRow } from "./BarRow";
import { PageHeader } from "./PageHeader";
import { StatCard } from "./StatCard";

const STATUS_BAR_COLOR: Record<string, string> = {
  queued: "bg-amber-500",
  approved: "bg-green-500",
  rejected: "bg-red-500",
};

export function Analytics() {
  const [reports, setReports] = useState<TriageResult[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    listReports()
      .then(setReports)
      .catch((err) => setError(err instanceof Error ? err.message : "Failed to load reports."))
      .finally(() => setLoading(false));
  }, []);

  const stats = useMemo(() => {
    const total = reports.length;
    const byCategory = new Map<string, number>();
    const byStatus = new Map<string, number>();
    let confidenceSum = 0;
    let confidenceCount = 0;
    let expeditedCount = 0;

    for (const r of reports) {
      const category = r.category ?? "unclassified";
      byCategory.set(category, (byCategory.get(category) ?? 0) + 1);
      byStatus.set(r.status, (byStatus.get(r.status) ?? 0) + 1);
      if (r.confidence !== null) {
        confidenceSum += r.confidence;
        confidenceCount += 1;
      }
      if (r.memo?.requires_expedited_reporting) expeditedCount += 1;
    }

    const approved = byStatus.get("approved") ?? 0;
    const rejected = byStatus.get("rejected") ?? 0;
    const reviewed = approved + rejected;

    return {
      total,
      byCategory: Array.from(byCategory.entries()).sort((a, b) => b[1] - a[1]),
      byStatus: Array.from(byStatus.entries()).sort((a, b) => b[1] - a[1]),
      avgConfidence: confidenceCount > 0 ? confidenceSum / confidenceCount : null,
      approvalRate: reviewed > 0 ? approved / reviewed : null,
      expeditedCount,
    };
  }, [reports]);

  if (loading) return <p className="text-slate-500">Loading...</p>;
  if (error) return <p className="text-red-600">{error}</p>;

  return (
    <div>
      <PageHeader title="Analytics" subtitle="Aggregate trends across all triaged deviation reports" />

      {stats.total === 0 ? (
        <p className="text-slate-500">No reports yet -- submit one to see analytics.</p>
      ) : (
        <>
          <div className="grid grid-cols-4 gap-4 mb-8">
            <StatCard
              icon={<ClipboardList className="w-5 h-5" />}
              label="Total reports"
              value={stats.total}
              accent="bg-slate-100 text-slate-600"
            />
            <StatCard
              icon={<Gauge className="w-5 h-5" />}
              label="Avg. confidence"
              value={stats.avgConfidence !== null ? `${Math.round(stats.avgConfidence * 100)}%` : "-"}
              accent="bg-sky-50 text-sky-600"
            />
            <StatCard
              icon={<CheckCircle2 className="w-5 h-5" />}
              label="Approval rate"
              value={stats.approvalRate !== null ? `${Math.round(stats.approvalRate * 100)}%` : "-"}
              accent="bg-green-50 text-green-600"
            />
            <StatCard
              icon={<AlertTriangle className="w-5 h-5" />}
              label="Expedited reporting"
              value={stats.expeditedCount}
              accent="bg-red-50 text-red-600"
            />
          </div>

          <div className="grid grid-cols-2 gap-6">
            <div className="card">
              <h3 className="font-medium text-slate-800 mb-4">By category</h3>
              <div className="space-y-3">
                {stats.byCategory.map(([category, count]) => (
                  <BarRow
                    key={category}
                    label={category}
                    count={count}
                    total={stats.total}
                    color={CATEGORY_BAR_CLASS[category] ?? "bg-slate-400"}
                  />
                ))}
              </div>
            </div>

            <div className="card">
              <h3 className="font-medium text-slate-800 mb-4">By review status</h3>
              <div className="space-y-3">
                {stats.byStatus.map(([status, count]) => (
                  <BarRow
                    key={status}
                    label={status}
                    count={count}
                    total={stats.total}
                    color={STATUS_BAR_COLOR[status] ?? "bg-slate-400"}
                  />
                ))}
              </div>
            </div>
          </div>
        </>
      )}
    </div>
  );
}

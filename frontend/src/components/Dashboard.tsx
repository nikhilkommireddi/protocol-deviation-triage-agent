import { useEffect, useMemo, useState } from "react";
import { AlertTriangle, Building2, ClipboardCheck, ClipboardList, FolderOpen, ShieldAlert } from "lucide-react";
import { listReports, listSites } from "../api";
import type { ManagedSite, TriageResult } from "../types";
import { attentionLevel, categoryBreakdown, isOpenReport, monthlyTrend, needsCapa } from "../lib/deviationStats";
import { PageHeader } from "./PageHeader";
import { StatCard } from "./StatCard";
import { TrendChart } from "./charts/TrendChart";
import { SeverityDonut } from "./charts/SeverityDonut";

const TREND_MONTHS = 6;

export function Dashboard() {
  const [reports, setReports] = useState<TriageResult[]>([]);
  const [sites, setSites] = useState<ManagedSite[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([listReports(), listSites()])
      .then(([r, s]) => {
        setReports(r);
        setSites(s);
      })
      .catch((err) => setError(err instanceof Error ? err.message : "Failed to load dashboard data."))
      .finally(() => setLoading(false));
  }, []);

  const stats = useMemo(() => {
    return {
      total: reports.length,
      open: reports.filter(isOpenReport).length,
      major: reports.filter((r) => r.category === "major").length,
      capaRequired: reports.filter(needsCapa).length,
      pendingReview: reports.filter((r) => r.status === "queued").length,
      sitesMonitored: sites.length,
    };
  }, [reports, sites]);

  const trend = useMemo(() => monthlyTrend(reports, TREND_MONTHS), [reports]);
  const severityBreakdown = useMemo(() => categoryBreakdown(reports), [reports]);

  const sitesRequiringAttention = useMemo(() => {
    const bySite = new Map<string, { major: number; open: number }>();
    for (const r of reports) {
      const entry = bySite.get(r.site_id) ?? { major: 0, open: 0 };
      if (r.category === "major") entry.major += 1;
      if (isOpenReport(r)) entry.open += 1;
      bySite.set(r.site_id, entry);
    }
    const siteNameById = new Map(sites.map((s) => [s.site_id, s.name]));
    return Array.from(bySite.entries())
      .filter(([, counts]) => counts.major > 0 || counts.open > 0)
      .sort((a, b) => b[1].major - a[1].major || b[1].open - a[1].open)
      .slice(0, 5)
      .map(([siteId, counts]) => ({
        siteId,
        name: siteNameById.get(siteId) ?? siteId,
        ...counts,
      }));
  }, [reports, sites]);

  if (loading) return <p className="text-slate-500">Loading...</p>;
  if (error) return <p className="text-red-600">{error}</p>;

  return (
    <div>
      <PageHeader title="Dashboard" subtitle="Overview of protocol deviations across your studies" />

      {stats.total === 0 ? (
        <p className="text-slate-500">No reports yet -- submit one to see the dashboard populate.</p>
      ) : (
        <>
          <div className="grid grid-cols-3 lg:grid-cols-6 gap-4 mb-8">
            <StatCard
              icon={<ClipboardList className="w-5 h-5" />}
              label="Total Deviations"
              value={stats.total}
              accent="bg-slate-100 text-slate-600"
            />
            <StatCard
              icon={<FolderOpen className="w-5 h-5" />}
              label="Open Deviations"
              value={stats.open}
              accent="bg-sky-50 text-sky-600"
            />
            <StatCard
              icon={<AlertTriangle className="w-5 h-5" />}
              label="Major Deviations"
              value={stats.major}
              accent="bg-red-50 text-red-600"
            />
            <StatCard
              icon={<ClipboardCheck className="w-5 h-5" />}
              label="CAPA Required"
              value={stats.capaRequired}
              accent="bg-amber-50 text-amber-600"
            />
            <StatCard
              icon={<ShieldAlert className="w-5 h-5" />}
              label="Pending Review"
              value={stats.pendingReview}
              accent="bg-violet-50 text-violet-600"
            />
            <StatCard
              icon={<Building2 className="w-5 h-5" />}
              label="Sites Monitored"
              value={stats.sitesMonitored}
              accent="bg-green-50 text-green-600"
            />
          </div>

          <div className="grid grid-cols-3 gap-6">
            <div className="card col-span-2">
              <h3 className="font-medium text-slate-800 mb-4">Deviation trends</h3>
              <TrendChart data={trend} />
            </div>

            <div className="card">
              <h3 className="font-medium text-slate-800 mb-4">Severity distribution</h3>
              <SeverityDonut data={severityBreakdown} total={stats.total} />
            </div>
          </div>

          <div className="card mt-6">
            <h3 className="font-medium text-slate-800 mb-4">Sites requiring attention</h3>
            {sitesRequiringAttention.length === 0 ? (
              <p className="text-sm text-slate-500">No sites currently show a major or open deviation.</p>
            ) : (
              <ul className="space-y-3">
                {sitesRequiringAttention.map(({ siteId, name, major, open }) => {
                  const level = attentionLevel(major);
                  return (
                    <li
                      key={siteId}
                      className="flex items-center justify-between border-b border-slate-100 last:border-0 pb-3 last:pb-0"
                    >
                      <div>
                        <p className="text-sm font-medium text-slate-800">{name}</p>
                        <p className="text-xs text-slate-500">
                          {major} major / {open} open deviation{open === 1 ? "" : "s"}
                        </p>
                      </div>
                      <span className={level.className}>{level.label}</span>
                    </li>
                  );
                })}
              </ul>
            )}
          </div>
        </>
      )}
    </div>
  );
}

import { useEffect, useMemo, useState } from "react";
import { AlertTriangle, Building2, ClipboardCheck, ClipboardList, FolderOpen } from "lucide-react";
import { listReports, listSites } from "../api";
import type { ManagedSite, TriageResult } from "../types";
import { CATEGORY_BAR_CLASS, categoryBadgeClass, statusBadgeClass } from "../lib/badges";
import {
  attentionLevel,
  categoryBreakdown,
  isOpenReport,
  monthlyTrend,
  needsCapa,
} from "../lib/deviationStats";
import { useAuth } from "../context/AuthContext";
import { can } from "../lib/permissions";
import { BarRow } from "./BarRow";
import { PageHeader } from "./PageHeader";
import { ReportDetail } from "./ReportDetail";
import { StatCard } from "./StatCard";
import { TrendChart } from "./charts/TrendChart";

const TREND_MONTHS = 6;
const RECENT_LIMIT = 8;

export function Sites() {
  const { user } = useAuth();
  const [reports, setReports] = useState<TriageResult[]>([]);
  const [sites, setSites] = useState<ManagedSite[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedSiteId, setSelectedSiteId] = useState<string | null>(user?.siteId ?? null);

  async function refresh() {
    setLoading(true);
    setError(null);
    try {
      const [r, s] = await Promise.all([listReports(), listSites()]);
      setReports(r);
      setSites(s);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load site data.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    refresh();
  }, []);

  const siteSummaries = useMemo(() => {
    const bySite = new Map<string, { total: number; major: number }>();
    for (const r of reports) {
      const entry = bySite.get(r.site_id) ?? { total: 0, major: 0 };
      entry.total += 1;
      if (r.category === "major") entry.major += 1;
      bySite.set(r.site_id, entry);
    }
    return sites
      .map((site) => ({
        site,
        total: bySite.get(site.site_id)?.total ?? 0,
        major: bySite.get(site.site_id)?.major ?? 0,
      }))
      .sort((a, b) => b.major - a.major || b.total - a.total);
  }, [sites, reports]);

  if (loading) return <p className="text-slate-500">Loading...</p>;
  if (error) return <p className="text-red-600">{error}</p>;

  // Site Coordinators go straight to their own site's history -- see
  // lib/permissions.ts's ROLE_INFO, which already documents this as their
  // capability. Everyone else picks a site from the list first.
  if (user?.siteId) {
    const site = sites.find((s) => s.site_id === user.siteId);
    if (!site) return <p className="text-slate-500">Your site could not be found.</p>;
    return (
      <SiteDetail
        site={site}
        reports={reports.filter((r) => r.site_id === site.site_id)}
        onReportChanged={refresh}
      />
    );
  }

  if (selectedSiteId) {
    const site = sites.find((s) => s.site_id === selectedSiteId);
    if (site) {
      return (
        <SiteDetail
          site={site}
          reports={reports.filter((r) => r.site_id === site.site_id)}
          onBack={() => setSelectedSiteId(null)}
          onReportChanged={refresh}
        />
      );
    }
  }

  return (
    <div>
      <PageHeader title="Sites" subtitle="Deviation history and trends by site" />

      {siteSummaries.length === 0 ? (
        <p className="text-slate-500">No sites on file yet.</p>
      ) : (
        <div className="grid grid-cols-2 gap-4">
          {siteSummaries.map(({ site, total, major }) => {
            const level = attentionLevel(major);
            return (
              <button
                key={site.site_id}
                type="button"
                onClick={() => setSelectedSiteId(site.site_id)}
                className="card text-left hover:border-sky-300 transition-colors"
              >
                <div className="flex items-center justify-between mb-2">
                  <div className="flex items-center gap-2">
                    <Building2 className="w-4 h-4 text-slate-400" />
                    <span className="font-medium text-slate-800">{site.name}</span>
                  </div>
                  <span className={level.className}>{level.label}</span>
                </div>
                <p className="text-xs text-slate-500 mb-2">
                  Site {site.site_id} {site.protocol_id ? `/ ${site.protocol_id}` : ""}
                </p>
                <p className="text-sm text-slate-600">
                  {total} deviation{total === 1 ? "" : "s"} / {major} major
                </p>
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}

function SiteDetail({
  site,
  reports,
  onBack,
  onReportChanged,
}: {
  site: ManagedSite;
  reports: TriageResult[];
  onBack?: () => void;
  onReportChanged: () => void;
}) {
  const { user } = useAuth();
  const [selectedId, setSelectedId] = useState<string | null>(null);

  const stats = useMemo(
    () => ({
      total: reports.length,
      major: reports.filter((r) => r.category === "major").length,
      open: reports.filter(isOpenReport).length,
      capaRequired: reports.filter(needsCapa).length,
    }),
    [reports],
  );

  const trend = useMemo(() => monthlyTrend(reports, TREND_MONTHS), [reports]);
  const breakdown = useMemo(() => categoryBreakdown(reports), [reports]);
  const recent = useMemo(
    () =>
      [...reports]
        .sort((a, b) => (a.created_at < b.created_at ? 1 : -1))
        .slice(0, RECENT_LIMIT),
    [reports],
  );

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <div>
          <div className="flex items-center gap-2">
            {onBack && (
              <button type="button" onClick={onBack} className="text-sm text-sky-600 hover:underline mr-1">
                Sites
              </button>
            )}
            <h1 className="text-2xl font-bold text-slate-900">{site.name}</h1>
            <span className={attentionLevel(stats.major).className}>
              {attentionLevel(stats.major).label}
            </span>
          </div>
          <p className="text-sm text-slate-500 mt-1">
            Site {site.site_id} {site.protocol_id ? `/ ${site.protocol_id}` : ""}
          </p>
        </div>
      </div>

      {reports.length === 0 ? (
        <p className="text-slate-500">No deviations on file for this site yet.</p>
      ) : (
        <>
          <div className="grid grid-cols-4 gap-4 mb-8">
            <StatCard
              icon={<ClipboardList className="w-5 h-5" />}
              label="Total Deviations"
              value={stats.total}
              accent="bg-slate-100 text-slate-600"
            />
            <StatCard
              icon={<AlertTriangle className="w-5 h-5" />}
              label="Major"
              value={stats.major}
              accent="bg-red-50 text-red-600"
            />
            <StatCard
              icon={<FolderOpen className="w-5 h-5" />}
              label="Open"
              value={stats.open}
              accent="bg-sky-50 text-sky-600"
            />
            <StatCard
              icon={<ClipboardCheck className="w-5 h-5" />}
              label="CAPA Required"
              value={stats.capaRequired}
              accent="bg-amber-50 text-amber-600"
            />
          </div>

          <div className="grid grid-cols-3 gap-6 mb-6">
            <div className="card col-span-2">
              <h3 className="font-medium text-slate-800 mb-4">Deviation trend</h3>
              <TrendChart data={trend} />
            </div>
            <div className="card">
              <h3 className="font-medium text-slate-800 mb-4">By category</h3>
              <div className="space-y-3">
                {breakdown.map(({ category, count }) => (
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
          </div>

          <div className="card overflow-x-auto mb-3">
            <h3 className="font-medium text-slate-800 mb-3">Recent deviations</h3>
            <table className="min-w-full text-sm">
              <thead>
                <tr className="text-left text-slate-500 border-b border-slate-200">
                  <th className="py-2 pr-4">Report ID</th>
                  <th className="py-2 pr-4">Subject</th>
                  <th className="py-2 pr-4">Category</th>
                  <th className="py-2 pr-4">Status</th>
                  <th className="py-2 pr-4">Created</th>
                </tr>
              </thead>
              <tbody>
                {recent.map((r) => (
                  <tr
                    key={r.report_id}
                    onClick={() => setSelectedId(r.report_id)}
                    className={
                      "cursor-pointer border-b border-slate-100 hover:bg-slate-50 " +
                      (selectedId === r.report_id ? "bg-sky-50" : "")
                    }
                  >
                    <td className="py-2 pr-4 font-mono text-xs">{r.report_id.slice(0, 8)}</td>
                    <td className="py-2 pr-4">{r.subject_id}</td>
                    <td className="py-2 pr-4">
                      <span className={categoryBadgeClass(r.category)}>{r.category ?? "-"}</span>
                    </td>
                    <td className="py-2 pr-4">
                      <span className={statusBadgeClass(r.status)}>{r.status}</span>
                    </td>
                    <td className="py-2 pr-4 text-xs text-slate-500">{r.created_at}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {selectedId && (
            <ReportDetail
              reportId={selectedId}
              canEdit={can(user, "review.edit")}
              canDecide={can(user, "review.decide")}
              onReviewed={onReportChanged}
            />
          )}
        </>
      )}
    </div>
  );
}

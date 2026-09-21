import { useEffect, useMemo, useState } from "react";
import { AlertTriangle, Building2, ClipboardCheck, ClipboardList, FolderOpen, ShieldAlert } from "lucide-react";
import { listReports, listSites } from "../api";
import type { ManagedSite, TriageResult } from "../types";
import { CATEGORY_COLOR } from "../lib/badges";
import { PageHeader } from "./PageHeader";
import { StatCard } from "./StatCard";

const TREND_MONTHS = 6;
const CATEGORIES = ["major", "minor", "technical", "administrative", "unreported"];

function needsCapa(r: TriageResult): boolean {
  const actions = r.memo?.recommended_capa_actions ?? [];
  if (actions.length === 0) return false;
  const status = r.capa_actions_status ?? [];
  return !actions.every((_, i) => status[i] === true);
}

function isOpen(r: TriageResult): boolean {
  return r.status !== "approved" && r.status !== "rejected";
}

function monthLabel(date: Date): string {
  return date.toLocaleDateString(undefined, { month: "short" });
}

function attentionLevel(majorCount: number): { label: string; className: string } {
  if (majorCount >= 3) return { label: "High", className: "badge badge-red" };
  if (majorCount >= 1) return { label: "Medium", className: "badge badge-amber" };
  return { label: "Low", className: "badge badge-slate" };
}

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
      open: reports.filter(isOpen).length,
      major: reports.filter((r) => r.category === "major").length,
      capaRequired: reports.filter(needsCapa).length,
      pendingReview: reports.filter((r) => r.status === "queued").length,
      sitesMonitored: sites.length,
    };
  }, [reports, sites]);

  const trend = useMemo(() => {
    const now = new Date();
    const buckets: { key: string; label: string; count: number }[] = [];
    for (let i = TREND_MONTHS - 1; i >= 0; i--) {
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
  }, [reports]);

  const severityBreakdown = useMemo(() => {
    const counts = new Map<string, number>();
    for (const r of reports) {
      const cat = r.category ?? "unreported";
      counts.set(cat, (counts.get(cat) ?? 0) + 1);
    }
    return CATEGORIES.map((cat) => ({ category: cat, count: counts.get(cat) ?? 0 })).filter(
      (c) => c.count > 0,
    );
  }, [reports]);

  const sitesRequiringAttention = useMemo(() => {
    const bySite = new Map<string, { major: number; open: number }>();
    for (const r of reports) {
      const entry = bySite.get(r.site_id) ?? { major: 0, open: 0 };
      if (r.category === "major") entry.major += 1;
      if (isOpen(r)) entry.open += 1;
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

function TrendChart({ data }: { data: { label: string; count: number }[] }) {
  const width = 480;
  const height = 140;
  const padding = 24;
  const max = Math.max(1, ...data.map((d) => d.count));
  const stepX = (width - padding * 2) / Math.max(1, data.length - 1);

  const points = data.map((d, i) => {
    const x = padding + i * stepX;
    const y = height - padding - (d.count / max) * (height - padding * 2);
    return { x, y, ...d };
  });

  const path = points.map((p, i) => `${i === 0 ? "M" : "L"}${p.x},${p.y}`).join(" ");

  return (
    <svg viewBox={`0 0 ${width} ${height}`} className="w-full h-36">
      <path d={path} fill="none" stroke="#0284c7" strokeWidth={2} />
      {points.map((p) => (
        <circle key={p.label + p.x} cx={p.x} cy={p.y} r={3} fill="#0284c7" />
      ))}
      {points.map((p) => (
        <text key={`label-${p.label}-${p.x}`} x={p.x} y={height - 4} fontSize={10} fill="#64748b" textAnchor="middle">
          {p.label}
        </text>
      ))}
    </svg>
  );
}

function SeverityDonut({ data, total }: { data: { category: string; count: number }[]; total: number }) {
  const radius = 40;
  const circumference = 2 * Math.PI * radius;
  let offset = 0;

  return (
    <div className="flex items-center gap-4">
      <svg viewBox="0 0 100 100" className="w-28 h-28 shrink-0 -rotate-90">
        <circle cx="50" cy="50" r={radius} fill="none" stroke="#e2e8f0" strokeWidth={14} />
        {data.map(({ category, count }) => {
          const fraction = count / total;
          const dash = fraction * circumference;
          const circle = (
            <circle
              key={category}
              cx="50"
              cy="50"
              r={radius}
              fill="none"
              stroke={CATEGORY_COLOR[category] ?? "#94a3b8"}
              strokeWidth={14}
              strokeDasharray={`${dash} ${circumference - dash}`}
              strokeDashoffset={-offset}
            />
          );
          offset += dash;
          return circle;
        })}
      </svg>
      <div className="space-y-1.5">
        {data.map(({ category, count }) => (
          <div key={category} className="flex items-center gap-2 text-xs">
            <span
              className="w-2.5 h-2.5 rounded-full shrink-0"
              style={{ backgroundColor: CATEGORY_COLOR[category] ?? "#94a3b8" }}
            />
            <span className="capitalize text-slate-700">{category}</span>
            <span className="text-slate-400">({count})</span>
          </div>
        ))}
      </div>
    </div>
  );
}

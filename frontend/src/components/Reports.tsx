import { useEffect, useMemo, useState } from "react";
import {
  Building2,
  CalendarDays,
  ClipboardCheck,
  FileText,
  History,
  ListFilter,
} from "lucide-react";
import { getAllAuditEvents, listReports, listSites } from "../api";
import type { AuditEvent, ManagedSite, TriageResult } from "../types";
import { downloadCsv } from "../lib/csvExport";
import { categoryBreakdown, monthlyTrend } from "../lib/deviationStats";
import { PageHeader } from "./PageHeader";

const DEVIATION_COLUMNS = [
  "Report ID",
  "Subject ID",
  "Category",
  "Status",
  "CAPA Status",
  "Deviation Date",
  "Discovery Date",
  "Created At",
];

function deviationRow(r: TriageResult): unknown[] {
  return [
    r.report_id,
    r.subject_id,
    r.category ?? "",
    r.status,
    r.capa_status ?? "",
    r.deviation_date,
    r.discovery_date,
    r.created_at,
  ];
}

export function Reports() {
  const [reports, setReports] = useState<TriageResult[]>([]);
  const [sites, setSites] = useState<ManagedSite[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [generating, setGenerating] = useState<string | null>(null);

  const [selectedSiteId, setSelectedSiteId] = useState("");
  const [selectedProtocolId, setSelectedProtocolId] = useState("");

  const [filterSite, setFilterSite] = useState("");
  const [filterCategory, setFilterCategory] = useState("");
  const [filterStatus, setFilterStatus] = useState("");
  const [filterFrom, setFilterFrom] = useState("");
  const [filterTo, setFilterTo] = useState("");

  useEffect(() => {
    Promise.all([listReports(), listSites()])
      .then(([r, s]) => {
        setReports(r);
        setSites(s);
      })
      .catch((err) => setError(err instanceof Error ? err.message : "Failed to load report data."))
      .finally(() => setLoading(false));
  }, []);

  const protocolIds = useMemo(
    () => Array.from(new Set(reports.map((r) => r.protocol_id))).sort(),
    [reports],
  );

  async function withGenerating(key: string, fn: () => void | Promise<void>) {
    setGenerating(key);
    try {
      await fn();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to generate report.");
    } finally {
      setGenerating(null);
    }
  }

  function generateSiteReport() {
    if (!selectedSiteId) return;
    const rows = reports.filter((r) => r.site_id === selectedSiteId).map(deviationRow);
    downloadCsv(`site-deviation-report-${selectedSiteId}.csv`, DEVIATION_COLUMNS, rows);
  }

  function generateStudyReport() {
    if (!selectedProtocolId) return;
    const rows = reports.filter((r) => r.protocol_id === selectedProtocolId).map(deviationRow);
    downloadCsv(`study-deviation-report-${selectedProtocolId}.csv`, DEVIATION_COLUMNS, rows);
  }

  function generateCapaReport() {
    const withMemo = reports.filter((r) => r.memo);
    const rows = withMemo.map((r) => [
      r.report_id,
      r.protocol_id,
      r.site_id,
      r.category ?? "",
      r.capa_status ?? "",
      r.memo?.responsible_party ?? "",
      r.memo?.target_resolution_date ?? "",
      r.memo?.requires_expedited_reporting ? "Yes" : "No",
    ]);
    downloadCsv(
      "capa-report.csv",
      ["Report ID", "Protocol ID", "Site ID", "Category", "CAPA Status", "Owner", "Due Date", "Expedited"],
      rows,
    );
  }

  function generateMonthlySummary() {
    const trend = monthlyTrend(reports, 6);
    const breakdown = categoryBreakdown(reports);
    const rows: unknown[][] = [
      ["Month", "Count"],
      ...trend.map((t) => [t.label, t.count]),
      [],
      ["Category", "Count"],
      ...breakdown.map((c) => [c.category, c.count]),
    ];
    downloadCsv("monthly-summary.csv", [], rows);
  }

  async function generateAuditReport() {
    const events: AuditEvent[] = await getAllAuditEvents();
    const rows = events.map((e) => [
      e.event_id,
      e.report_id,
      e.event_type,
      e.description,
      e.actor_name ?? "",
      e.actor_role ?? "",
      e.created_at,
    ]);
    downloadCsv(
      "audit-report.csv",
      ["Event ID", "Report ID", "Event Type", "Description", "Actor Name", "Actor Role", "Created At"],
      rows,
    );
  }

  function generateCustomReport() {
    const rows = reports
      .filter((r) => !filterSite || r.site_id === filterSite)
      .filter((r) => !filterCategory || r.category === filterCategory)
      .filter((r) => !filterStatus || r.status === filterStatus)
      .filter((r) => !filterFrom || r.deviation_date >= filterFrom)
      .filter((r) => !filterTo || r.deviation_date <= filterTo)
      .map(deviationRow);
    downloadCsv("custom-report.csv", DEVIATION_COLUMNS, rows);
  }

  if (loading) return <p className="text-slate-500">Loading...</p>;

  return (
    <div>
      <PageHeader title="Reports" subtitle="Generate CSV exports for sites, studies, CAPA, and audit history" />

      {error && <p className="text-red-600 text-sm mb-4">{error}</p>}

      {reports.length === 0 ? (
        <p className="text-slate-500">No reports yet -- nothing to export.</p>
      ) : (
        <div className="grid grid-cols-2 gap-4">
          <ReportCard
            icon={<Building2 className="w-5 h-5" />}
            title="Site Deviation Report"
            description="All deviations for a specific site."
          >
            <select
              className="input mb-3"
              value={selectedSiteId}
              onChange={(e) => setSelectedSiteId(e.target.value)}
            >
              <option value="">Select a site...</option>
              {sites.map((s) => (
                <option key={s.site_id} value={s.site_id}>
                  {s.name} ({s.site_id})
                </option>
              ))}
            </select>
            <button
              className="btn-primary"
              disabled={!selectedSiteId || generating === "site"}
              onClick={() => withGenerating("site", generateSiteReport)}
            >
              Generate
            </button>
          </ReportCard>

          <ReportCard
            icon={<FileText className="w-5 h-5" />}
            title="Study Deviation Report"
            description="All deviations for a specific protocol."
          >
            <select
              className="input mb-3"
              value={selectedProtocolId}
              onChange={(e) => setSelectedProtocolId(e.target.value)}
            >
              <option value="">Select a protocol...</option>
              {protocolIds.map((id) => (
                <option key={id} value={id}>
                  {id}
                </option>
              ))}
            </select>
            <button
              className="btn-primary"
              disabled={!selectedProtocolId || generating === "study"}
              onClick={() => withGenerating("study", generateStudyReport)}
            >
              Generate
            </button>
          </ReportCard>

          <ReportCard
            icon={<ClipboardCheck className="w-5 h-5" />}
            title="CAPA Report"
            description="Overview of every CAPA plan -- category, status, owner, due date."
          >
            <button
              className="btn-primary"
              disabled={generating === "capa"}
              onClick={() => withGenerating("capa", generateCapaReport)}
            >
              Generate
            </button>
          </ReportCard>

          <ReportCard
            icon={<CalendarDays className="w-5 h-5" />}
            title="Monthly Summary"
            description="Deviation counts by month and by category."
          >
            <button
              className="btn-primary"
              disabled={generating === "monthly"}
              onClick={() => withGenerating("monthly", generateMonthlySummary)}
            >
              Generate
            </button>
          </ReportCard>

          <ReportCard
            icon={<History className="w-5 h-5" />}
            title="Audit Report"
            description="Complete audit history across every deviation."
          >
            <button
              className="btn-primary"
              disabled={generating === "audit"}
              onClick={() => withGenerating("audit", generateAuditReport)}
            >
              Generate
            </button>
          </ReportCard>

          <ReportCard
            icon={<ListFilter className="w-5 h-5" />}
            title="Custom Report"
            description="Filter by site, category, status, and date range."
          >
            <div className="grid grid-cols-2 gap-2 mb-3">
              <select className="input" value={filterSite} onChange={(e) => setFilterSite(e.target.value)}>
                <option value="">Any site</option>
                {sites.map((s) => (
                  <option key={s.site_id} value={s.site_id}>
                    {s.name}
                  </option>
                ))}
              </select>
              <select
                className="input"
                value={filterCategory}
                onChange={(e) => setFilterCategory(e.target.value)}
              >
                <option value="">Any category</option>
                {["major", "minor", "technical", "administrative", "unreported"].map((c) => (
                  <option key={c} value={c}>
                    {c}
                  </option>
                ))}
              </select>
              <select className="input" value={filterStatus} onChange={(e) => setFilterStatus(e.target.value)}>
                <option value="">Any status</option>
                {Array.from(new Set(reports.map((r) => r.status))).map((s) => (
                  <option key={s} value={s}>
                    {s}
                  </option>
                ))}
              </select>
              <div className="flex gap-2">
                <input
                  type="date"
                  className="input"
                  value={filterFrom}
                  onChange={(e) => setFilterFrom(e.target.value)}
                  aria-label="From date"
                />
                <input
                  type="date"
                  className="input"
                  value={filterTo}
                  onChange={(e) => setFilterTo(e.target.value)}
                  aria-label="To date"
                />
              </div>
            </div>
            <button
              className="btn-primary"
              disabled={generating === "custom"}
              onClick={() => withGenerating("custom", generateCustomReport)}
            >
              Generate
            </button>
          </ReportCard>
        </div>
      )}
    </div>
  );
}

function ReportCard({
  icon,
  title,
  description,
  children,
}: {
  icon: React.ReactNode;
  title: string;
  description: string;
  children: React.ReactNode;
}) {
  return (
    <div className="card">
      <div className="flex items-center gap-2 mb-1">
        <span className="text-sky-600">{icon}</span>
        <h3 className="font-medium text-slate-800">{title}</h3>
      </div>
      <p className="text-xs text-slate-500 mb-3">{description}</p>
      {children}
    </div>
  );
}

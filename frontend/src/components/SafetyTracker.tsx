import { useEffect, useMemo, useState } from "react";
import { AlertTriangle, ShieldAlert, Siren } from "lucide-react";
import { listReports } from "../api";
import type { TriageResult } from "../types";
import { categoryBadgeClass, statusBadgeClass } from "../lib/badges";
import { useAuth } from "../context/AuthContext";
import { can } from "../lib/permissions";
import { PageHeader } from "./PageHeader";
import { ReportDetail } from "./ReportDetail";
import { StatCard } from "./StatCard";

export function SafetyTracker() {
  const { user } = useAuth();
  const [reports, setReports] = useState<TriageResult[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);

  async function refresh() {
    setLoading(true);
    setError(null);
    try {
      setReports(await listReports());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load reports.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    refresh();
  }, []);

  const flagged = useMemo(
    () => reports.filter((r) => r.category === "major" || r.memo?.requires_expedited_reporting),
    [reports],
  );

  if (loading) return <p className="text-slate-500">Loading...</p>;
  if (error) return <p className="text-red-600">{error}</p>;

  const stats = {
    total: flagged.length,
    expedited: flagged.filter((r) => r.memo?.requires_expedited_reporting).length,
    pending: flagged.filter((r) => r.status === "queued").length,
  };

  return (
    <div>
      <PageHeader
        title="Safety Tracker"
        subtitle="Major-category and expedited-reporting deviations, separated from the general queue"
      />

      {flagged.length === 0 ? (
        <p className="text-slate-500">No safety-flagged deviations on file.</p>
      ) : (
        <>
          <div className="grid grid-cols-3 gap-4 mb-6">
            <StatCard
              icon={<ShieldAlert className="w-5 h-5" />}
              label="Flagged cases"
              value={stats.total}
              accent="bg-red-50 text-red-600"
            />
            <StatCard
              icon={<Siren className="w-5 h-5" />}
              label="Expedited reporting required"
              value={stats.expedited}
              accent="bg-amber-50 text-amber-600"
            />
            <StatCard
              icon={<AlertTriangle className="w-5 h-5" />}
              label="Awaiting review"
              value={stats.pending}
              accent="bg-slate-100 text-slate-600"
            />
          </div>

          <div className="card overflow-x-auto mb-3">
            <table className="min-w-full text-sm">
              <thead>
                <tr className="text-left text-slate-500 border-b border-slate-200">
                  <th className="py-2 pr-4">Report ID</th>
                  <th className="py-2 pr-4">Protocol</th>
                  <th className="py-2 pr-4">Subject</th>
                  <th className="py-2 pr-4">Category</th>
                  <th className="py-2 pr-4">Expedited</th>
                  <th className="py-2 pr-4">Status</th>
                  <th className="py-2 pr-4">Created</th>
                </tr>
              </thead>
              <tbody>
                {flagged.map((r) => (
                  <tr
                    key={r.report_id}
                    onClick={() => setSelectedId(r.report_id)}
                    className={
                      "cursor-pointer border-b border-slate-100 hover:bg-slate-50 " +
                      (selectedId === r.report_id ? "bg-sky-50" : "")
                    }
                  >
                    <td className="py-2 pr-4 font-mono text-xs">{r.report_id.slice(0, 8)}</td>
                    <td className="py-2 pr-4">{r.protocol_id}</td>
                    <td className="py-2 pr-4">{r.subject_id}</td>
                    <td className="py-2 pr-4">
                      <span className={categoryBadgeClass(r.category)}>{r.category ?? "-"}</span>
                    </td>
                    <td className="py-2 pr-4">
                      {r.memo?.requires_expedited_reporting ? (
                        <span className="badge badge-red">Yes</span>
                      ) : (
                        <span className="text-slate-400">No</span>
                      )}
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
              onReviewed={refresh}
            />
          )}
        </>
      )}
    </div>
  );
}

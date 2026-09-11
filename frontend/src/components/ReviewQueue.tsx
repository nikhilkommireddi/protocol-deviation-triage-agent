import { useEffect, useMemo, useState } from "react";
import { listReports } from "../api";
import type { TriageResult } from "../types";
import { ReportDetail } from "./ReportDetail";

export function ReviewQueue() {
  const [reports, setReports] = useState<TriageResult[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [statusFilter, setStatusFilter] = useState<Set<string>>(new Set());
  const [selectedId, setSelectedId] = useState<string | null>(null);

  async function refresh() {
    setLoading(true);
    setError(null);
    try {
      const data = await listReports();
      setReports(data);
      setStatusFilter((prev) => {
        const allStatuses = new Set(data.map((r) => r.status));
        return prev.size === 0 ? allStatuses : prev;
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load reports.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    refresh();
  }, []);

  const allStatuses = useMemo(
    () => Array.from(new Set(reports.map((r) => r.status))).sort(),
    [reports],
  );
  const filtered = reports.filter((r) => statusFilter.has(r.status));

  function toggleStatus(status: string) {
    setStatusFilter((prev) => {
      const next = new Set(prev);
      if (next.has(status)) next.delete(status);
      else next.add(status);
      return next;
    });
  }

  if (loading) return <p className="text-slate-500">Loading...</p>;
  if (error) return <p className="text-red-600">{error}</p>;

  return (
    <div>
      <h2 className="text-lg font-semibold text-slate-800 mb-4">Review queue</h2>

      {reports.length === 0 ? (
        <p className="text-slate-500">No reports yet -- submit one on the first tab.</p>
      ) : (
        <>
          <div className="flex gap-2 mb-4 flex-wrap">
            {allStatuses.map((status) => (
              <button
                key={status}
                onClick={() => toggleStatus(status)}
                className={
                  statusFilter.has(status)
                    ? "rounded-full bg-sky-100 text-sky-800 border border-sky-300 px-3 py-1 text-xs font-medium"
                    : "rounded-full bg-white text-slate-500 border border-slate-300 px-3 py-1 text-xs font-medium"
                }
              >
                {status}
              </button>
            ))}
          </div>

          <div className="card overflow-x-auto mb-6">
            <table className="min-w-full text-sm">
              <thead>
                <tr className="text-left text-slate-500 border-b border-slate-200">
                  <th className="py-2 pr-4">Report ID</th>
                  <th className="py-2 pr-4">Protocol</th>
                  <th className="py-2 pr-4">Subject</th>
                  <th className="py-2 pr-4">Category</th>
                  <th className="py-2 pr-4">Confidence</th>
                  <th className="py-2 pr-4">Status</th>
                  <th className="py-2 pr-4">Created</th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((r) => (
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
                    <td className="py-2 pr-4">{r.category ?? "-"}</td>
                    <td className="py-2 pr-4">
                      {r.confidence !== null ? r.confidence.toFixed(2) : "-"}
                    </td>
                    <td className="py-2 pr-4">{r.status}</td>
                    <td className="py-2 pr-4 text-xs text-slate-500">{r.created_at}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {selectedId && (
            <ReportDetail
              reportId={selectedId}
              onReviewed={() => {
                refresh();
              }}
            />
          )}
        </>
      )}
    </div>
  );
}

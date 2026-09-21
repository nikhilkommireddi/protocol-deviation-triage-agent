import { useEffect, useMemo, useState } from "react";
import { CheckCircle2, ClipboardList, Clock, Search, XCircle } from "lucide-react";
import { listReports } from "../api";
import type { TriageResult } from "../types";
import { categoryBadgeClass, statusBadgeClass } from "../lib/badges";
import { useAuth } from "../context/AuthContext";
import { can } from "../lib/permissions";
import { PageHeader } from "./PageHeader";
import { ReportDetail } from "./ReportDetail";
import { StatCard } from "./StatCard";

const PAGE_SIZE = 10;

export function ReviewQueue() {
  const { user } = useAuth();
  const [reports, setReports] = useState<TriageResult[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [statusFilter, setStatusFilter] = useState<Set<string>>(new Set());
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(0);
  const [selectedId, setSelectedId] = useState<string | null>(null);

  const canDecide = can(user, "review.decide");
  const canEdit = can(user, "review.edit");

  async function refresh() {
    setLoading(true);
    setError(null);
    try {
      const all = await listReports();
      // Site Coordinators only see their own site's deviations. This is a
      // demo-only client-side filter -- the backend returns every report to
      // anyone who calls it directly; there is no real enforcement here.
      const data = user?.siteId ? all.filter((r) => r.site_id === user.siteId) : all;
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

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    return reports.filter((r) => {
      if (!statusFilter.has(r.status)) return false;
      if (!q) return true;
      return (
        r.report_id.toLowerCase().includes(q) ||
        r.protocol_id.toLowerCase().includes(q) ||
        r.subject_id.toLowerCase().includes(q)
      );
    });
  }, [reports, statusFilter, search]);

  const pageCount = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE));
  const pageStart = page * PAGE_SIZE;
  const paged = filtered.slice(pageStart, pageStart + PAGE_SIZE);

  function toggleStatus(status: string) {
    setPage(0);
    setStatusFilter((prev) => {
      const next = new Set(prev);
      if (next.has(status)) next.delete(status);
      else next.add(status);
      return next;
    });
  }

  if (loading) return <p className="text-slate-500">Loading...</p>;
  if (error) return <p className="text-red-600">{error}</p>;

  const stats = {
    total: reports.length,
    pending: reports.filter((r) => r.status === "queued").length,
    approved: reports.filter((r) => r.status === "approved").length,
    rejected: reports.filter((r) => r.status === "rejected").length,
  };

  return (
    <div>
      <PageHeader title="Review Queue" subtitle="Triaged deviation reports awaiting or completing human review" />

      {reports.length === 0 ? (
        <p className="text-slate-500">No reports yet -- submit one from Submit New Deviation.</p>
      ) : (
        <>
          <div className="grid grid-cols-4 gap-4 mb-6">
            <StatCard
              icon={<ClipboardList className="w-5 h-5" />}
              label="Total"
              value={stats.total}
              accent="bg-slate-100 text-slate-600"
            />
            <StatCard
              icon={<Clock className="w-5 h-5" />}
              label="Pending review"
              value={stats.pending}
              accent="bg-amber-50 text-amber-600"
            />
            <StatCard
              icon={<CheckCircle2 className="w-5 h-5" />}
              label="Approved"
              value={stats.approved}
              accent="bg-green-50 text-green-600"
            />
            <StatCard
              icon={<XCircle className="w-5 h-5" />}
              label="Rejected"
              value={stats.rejected}
              accent="bg-red-50 text-red-600"
            />
          </div>

          <div className="flex items-center gap-3 mb-4 flex-wrap">
            <div className="relative">
              <Search className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
              <input
                className="input pl-9 w-64"
                placeholder="Search by report, protocol, subject..."
                value={search}
                onChange={(e) => {
                  setPage(0);
                  setSearch(e.target.value);
                }}
              />
            </div>
            <div className="flex gap-2 flex-wrap">
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
          </div>

          <div className="card overflow-x-auto mb-3">
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
                {paged.map((r) => (
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
                      {r.category ? (
                        <span className={categoryBadgeClass(r.category)}>{r.category}</span>
                      ) : (
                        "-"
                      )}
                    </td>
                    <td className="py-2 pr-4">
                      {r.confidence !== null ? r.confidence.toFixed(2) : "-"}
                    </td>
                    <td className="py-2 pr-4">
                      <span className={statusBadgeClass(r.status)}>{r.status}</span>
                    </td>
                    <td className="py-2 pr-4 text-xs text-slate-500">{r.created_at}</td>
                  </tr>
                ))}
                {paged.length === 0 && (
                  <tr>
                    <td colSpan={7} className="py-6 text-center text-slate-400">
                      No reports match the current filters.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>

          {pageCount > 1 && (
            <div className="flex items-center justify-between mb-6 text-sm text-slate-500">
              <span>
                Page {page + 1} of {pageCount} ({filtered.length} reports)
              </span>
              <div className="flex gap-2">
                <button
                  className="btn-secondary"
                  disabled={page === 0}
                  onClick={() => setPage((p) => Math.max(0, p - 1))}
                >
                  Previous
                </button>
                <button
                  className="btn-secondary"
                  disabled={page >= pageCount - 1}
                  onClick={() => setPage((p) => Math.min(pageCount - 1, p + 1))}
                >
                  Next
                </button>
              </div>
            </div>
          )}

          {selectedId && (
            <ReportDetail
              reportId={selectedId}
              canEdit={canEdit}
              canDecide={canDecide}
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

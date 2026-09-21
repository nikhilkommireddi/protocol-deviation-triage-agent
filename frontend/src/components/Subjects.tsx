import { useEffect, useMemo, useState } from "react";
import { User } from "lucide-react";
import { listReports } from "../api";
import type { TriageResult } from "../types";
import { categoryBadgeClass, statusBadgeClass } from "../lib/badges";
import { PageHeader } from "./PageHeader";

export function Subjects() {
  const [reports, setReports] = useState<TriageResult[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    listReports()
      .then(setReports)
      .catch((err) => setError(err instanceof Error ? err.message : "Failed to load reports."))
      .finally(() => setLoading(false));
  }, []);

  const bySubject = useMemo(() => {
    const groups = new Map<string, TriageResult[]>();
    for (const r of reports) {
      const list = groups.get(r.subject_id) ?? [];
      list.push(r);
      groups.set(r.subject_id, list);
    }
    return Array.from(groups.entries()).sort(([a], [b]) => a.localeCompare(b));
  }, [reports]);

  if (loading) return <p className="text-slate-500">Loading...</p>;
  if (error) return <p className="text-red-600">{error}</p>;

  return (
    <div>
      <PageHeader title="Subjects" subtitle="Deviations grouped by subject rather than by site" />

      {bySubject.length === 0 ? (
        <p className="text-slate-500">No reports yet.</p>
      ) : (
        <div className="space-y-4">
          {bySubject.map(([subjectId, subjectReports]) => (
            <div key={subjectId} className="card">
              <div className="flex items-center gap-2 mb-3">
                <User className="w-4 h-4 text-slate-400" />
                <h3 className="font-medium text-slate-800">{subjectId}</h3>
                <span className="text-xs text-slate-400">
                  {subjectReports.length} report{subjectReports.length === 1 ? "" : "s"}
                </span>
              </div>
              <div className="space-y-2">
                {subjectReports.map((r) => (
                  <div
                    key={r.report_id}
                    className="flex items-center justify-between text-sm border-t border-slate-100 pt-2 first:border-t-0 first:pt-0"
                  >
                    <div className="flex items-center gap-3">
                      <span className="font-mono text-xs text-slate-500">
                        {r.report_id.slice(0, 8)}
                      </span>
                      <span className="text-slate-600">{r.protocol_id}</span>
                      <span className={categoryBadgeClass(r.category)}>{r.category ?? "-"}</span>
                    </div>
                    <div className="flex items-center gap-3">
                      <span className="text-xs text-slate-400">{r.deviation_date}</span>
                      <span className={statusBadgeClass(r.status)}>{r.status}</span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

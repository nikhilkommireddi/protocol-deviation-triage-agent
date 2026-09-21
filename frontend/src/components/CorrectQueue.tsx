import { useEffect, useState } from "react";
import { CheckCircle2, Circle, Wrench } from "lucide-react";
import { listReports, updateCapaActionsStatus } from "../api";
import type { TriageResult } from "../types";
import { categoryBadgeClass } from "../lib/badges";
import { useAuth } from "../context/AuthContext";
import { can } from "../lib/permissions";
import { PageHeader } from "./PageHeader";

function isFullyCorrected(r: TriageResult): boolean {
  const actions = r.memo?.recommended_capa_actions ?? [];
  if (actions.length === 0) return false;
  const status = r.capa_actions_status ?? [];
  return actions.every((_, i) => status[i] === true);
}

export function CorrectQueue() {
  const { user } = useAuth();
  const canEdit = can(user, "correct.edit");
  const [reports, setReports] = useState<TriageResult[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    refresh();
  }, []);

  async function refresh() {
    setLoading(true);
    setError(null);
    try {
      const data = await listReports();
      setReports(data.filter((r) => r.status === "approved"));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load reports.");
    } finally {
      setLoading(false);
    }
  }

  function handleUpdated(updated: TriageResult) {
    setReports((prev) => prev.map((r) => (r.report_id === updated.report_id ? updated : r)));
  }

  if (loading) return <p className="text-slate-500">Loading...</p>;
  if (error) return <p className="text-red-600">{error}</p>;

  const open = reports.filter((r) => !isFullyCorrected(r));
  const closed = reports.filter((r) => isFullyCorrected(r));

  return (
    <div>
      <PageHeader
        title="Correct"
        subtitle="Track whether each approved memo's recommended CAPA actions actually get done"
      />

      {reports.length === 0 ? (
        <p className="text-slate-500">
          No approved reports yet -- approve one from Review to start tracking its CAPA actions
          here.
        </p>
      ) : (
        <div className="space-y-6">
          {open.length > 0 && (
            <div>
              <h3 className="text-sm font-medium text-slate-500 mb-3">Open ({open.length})</h3>
              <div className="space-y-3">
                {open.map((r) => (
                  <CorrectCard
                    key={r.report_id}
                    report={r}
                    canEdit={canEdit}
                    onUpdated={handleUpdated}
                  />
                ))}
              </div>
            </div>
          )}
          {closed.length > 0 && (
            <div>
              <h3 className="text-sm font-medium text-slate-500 mb-3">Closed ({closed.length})</h3>
              <div className="space-y-3">
                {closed.map((r) => (
                  <CorrectCard
                    key={r.report_id}
                    report={r}
                    canEdit={canEdit}
                    onUpdated={handleUpdated}
                  />
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function CorrectCard({
  report,
  canEdit,
  onUpdated,
}: {
  report: TriageResult;
  canEdit: boolean;
  onUpdated: (updated: TriageResult) => void;
}) {
  const actions = report.memo?.recommended_capa_actions ?? [];
  const [status, setStatus] = useState<boolean[]>(
    report.capa_actions_status ?? actions.map(() => false),
  );
  const [saving, setSaving] = useState(false);

  const closed = actions.length > 0 && actions.every((_, i) => status[i] === true);

  async function toggle(index: number) {
    const next = [...status];
    next[index] = !next[index];
    const previous = status;
    setStatus(next);
    setSaving(true);
    try {
      const updated = await updateCapaActionsStatus(report.report_id, next);
      onUpdated(updated);
    } catch {
      setStatus(previous);
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="card">
      <div className="flex items-center justify-between mb-3 flex-wrap gap-2">
        <div className="flex items-center gap-2">
          <Wrench className="w-4 h-4 text-slate-400" />
          <span className="font-mono text-xs text-slate-500">{report.report_id.slice(0, 8)}</span>
          <span className="text-sm text-slate-700">
            {report.protocol_id} / {report.subject_id}
          </span>
          <span className={categoryBadgeClass(report.category)}>{report.category}</span>
        </div>
        <div className="flex items-center gap-2">
          {!canEdit && <span className="text-[10px] uppercase tracking-wide text-slate-400">View only</span>}
          <span className={closed ? "badge badge-green" : "badge badge-amber"}>
            {closed ? "Closed" : "Open"}
          </span>
        </div>
      </div>
      {actions.length === 0 ? (
        <p className="text-sm text-slate-400">No CAPA actions recorded for this memo.</p>
      ) : (
        <ul className="space-y-2">
          {actions.map((action, i) => (
            <li key={i} className="flex items-start gap-2">
              <button
                type="button"
                onClick={() => toggle(i)}
                disabled={saving || !canEdit}
                className={"mt-0.5 shrink-0 " + (canEdit ? "" : "cursor-not-allowed")}
              >
                {status[i] ? (
                  <CheckCircle2 className="w-4 h-4 text-green-600" />
                ) : (
                  <Circle className="w-4 h-4 text-slate-300" />
                )}
              </button>
              <span
                className={"text-sm " + (status[i] ? "text-slate-400 line-through" : "text-slate-700")}
              >
                {action}
              </span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

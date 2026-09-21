import { useEffect, useState } from "react";
import { CheckCircle2, Download, FileText, ShieldAlert, XCircle } from "lucide-react";
import { getReport, reviewReport } from "../api";
import type { Memo, ReviewDecision, TriageResult } from "../types";
import { categoryBadgeClass, statusBadgeClass } from "../lib/badges";
import { generateReportPdf } from "../lib/pdfReport";
import { useAuth } from "../context/AuthContext";
import { AuditTrail } from "./AuditTrail";
import { ReasoningTrace } from "./ReasoningTrace";

const CATEGORIES = ["major", "minor", "technical", "administrative", "unreported"];

interface ReportDetailProps {
  reportId: string;
  onReviewed: () => void;
  /** Whether the current role may edit memo fields (an override). Defaults to true for callers that don't gate. */
  canEdit?: boolean;
  /** Whether the current role may Approve/Reject (a final decision). Defaults to true for callers that don't gate. */
  canDecide?: boolean;
}

const EMPTY_MEMO: Memo = {
  summary: "",
  root_cause_narrative: "",
  regulatory_citation: "",
  recommended_capa_actions: [],
  requires_expedited_reporting: false,
  responsible_party: "",
  target_resolution_date: "",
  reviewer_note: "",
};

export function ReportDetail({
  reportId,
  onReviewed,
  canEdit = true,
  canDecide = true,
}: ReportDetailProps) {
  const { user } = useAuth();
  const [record, setRecord] = useState<TriageResult | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const [memo, setMemo] = useState<Memo>(EMPTY_MEMO);
  const [actionsText, setActionsText] = useState("");
  const [category, setCategory] = useState<string>("");

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    getReport(reportId)
      .then((r) => {
        if (cancelled) return;
        setRecord(r);
        if (r.category) setCategory(r.category);
        if (r.memo) {
          setMemo(r.memo);
          setActionsText(r.memo.recommended_capa_actions.join("\n"));
        }
      })
      .catch((err) => {
        if (!cancelled) setError(err instanceof Error ? err.message : "Failed to load report.");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [reportId]);

  async function handleReview(status: ReviewDecision) {
    setSubmitting(true);
    setError(null);
    try {
      const editedMemo: Memo = {
        ...memo,
        recommended_capa_actions: actionsText
          .split("\n")
          .map((line) => line.trim())
          .filter(Boolean),
      };
      const updated = await reviewReport(reportId, {
        memo: editedMemo,
        status,
        category: category || undefined,
        actor_name: user?.name,
        actor_role: user?.role,
      });
      setRecord(updated);
      onReviewed();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Review submission failed.");
    } finally {
      setSubmitting(false);
    }
  }

  if (loading) return <p className="text-slate-500">Loading report...</p>;
  if (error && !record) return <p className="text-red-600">{error}</p>;
  if (!record) return null;

  return (
    <div className="card space-y-6">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div className="flex items-center gap-2">
          <FileText className="w-4 h-4 text-slate-400" />
          <span className="font-mono text-xs text-slate-500">{record.report_id.slice(0, 8)}</span>
          <span className={statusBadgeClass(record.status)}>{record.status}</span>
          {record.category && <span className={categoryBadgeClass(record.category)}>{record.category}</span>}
        </div>
        <button
          className="btn-secondary flex items-center gap-2"
          onClick={() => generateReportPdf(record)}
        >
          <Download className="w-4 h-4" />
          Download Report
        </button>
      </div>

      <div className="grid grid-cols-3 gap-6">
        <div className="col-span-2">
          <h3 className="font-medium text-slate-800 mb-1">
            Original report ({record.protocol_id} / {record.subject_id})
          </h3>
          <textarea className="input h-28" value={record.text} disabled />
          <p className="text-xs text-slate-500 mt-1">
            Deviation date: {record.deviation_date} | Discovery date: {record.discovery_date}
          </p>
        </div>

        <div>
          <h3 className="font-medium text-slate-800 mb-1">Classification</h3>
          {record.category ? (
            <>
              <label className="block text-sm mb-1">
                Category:{" "}
                {canEdit ? (
                  <select
                    className="input inline-block w-auto ml-1"
                    value={category}
                    onChange={(e) => setCategory(e.target.value)}
                  >
                    {CATEGORIES.map((cat) => (
                      <option key={cat} value={cat}>
                        {cat}
                      </option>
                    ))}
                  </select>
                ) : (
                  <span className="font-semibold">{record.category}</span>
                )}
              </label>
              <p className="text-sm">Confidence: {record.confidence?.toFixed(2)}</p>
              {(record.confidence ?? 1) < 0.6 && (
                <p className="text-sm text-amber-700 bg-amber-50 border border-amber-200 rounded px-2 py-1 mt-2 flex items-center gap-1.5">
                  <ShieldAlert className="w-4 h-4 shrink-0" />
                  Low confidence -- review the category assignment carefully.
                </p>
              )}
            </>
          ) : (
            <p className="text-sm text-slate-500">Not yet classified.</p>
          )}
        </div>
      </div>

      {record.capa_guidance && (
        <details className="rounded-md border border-slate-200 p-3">
          <summary className="cursor-pointer font-medium text-slate-700">CAPA guidance</summary>
          <div className="mt-2 text-sm space-y-1">
            <p>
              <span className="font-medium">Routing team:</span>{" "}
              {record.capa_guidance.routing_team}
            </p>
            <p>
              <span className="font-medium">Regulatory reference:</span>{" "}
              {record.capa_guidance.regulatory_reference}
            </p>
            <p className="font-medium">Required CAPA elements:</p>
            <ul className="list-disc list-inside">
              {record.capa_guidance.required_capa_elements.map((el) => (
                <li key={el}>{el}</li>
              ))}
            </ul>
          </div>
        </details>
      )}

      <ReasoningTrace result={record} />

      {record.memo ? (
        <div className="space-y-4 border-t border-slate-200 pt-4">
          <h3 className="font-medium text-slate-800">
            Drafted memo{" "}
            {canEdit ? "(edit as needed before approving)" : "(view only for your role)"}
          </h3>

          <Field label="Summary">
            <textarea
              className="input h-20"
              value={memo.summary}
              disabled={!canEdit}
              onChange={(e) => setMemo({ ...memo, summary: e.target.value })}
            />
          </Field>
          <Field label="Root cause narrative">
            <textarea
              className="input h-24"
              value={memo.root_cause_narrative}
              disabled={!canEdit}
              onChange={(e) => setMemo({ ...memo, root_cause_narrative: e.target.value })}
            />
          </Field>
          <Field label="Regulatory citation">
            <textarea
              className="input h-16"
              value={memo.regulatory_citation}
              disabled={!canEdit}
              onChange={(e) => setMemo({ ...memo, regulatory_citation: e.target.value })}
            />
          </Field>
          <Field label="Recommended CAPA actions (one per line)">
            <textarea
              className="input h-28"
              value={actionsText}
              disabled={!canEdit}
              onChange={(e) => setActionsText(e.target.value)}
            />
          </Field>

          <label className="flex items-center gap-2 text-sm text-slate-700">
            <input
              type="checkbox"
              checked={memo.requires_expedited_reporting}
              disabled={!canEdit}
              onChange={(e) =>
                setMemo({ ...memo, requires_expedited_reporting: e.target.checked })
              }
            />
            Requires expedited reporting
          </label>

          <div className="grid grid-cols-2 gap-4">
            <Field label="Responsible party">
              <input
                className="input"
                value={memo.responsible_party}
                disabled={!canEdit}
                onChange={(e) => setMemo({ ...memo, responsible_party: e.target.value })}
              />
            </Field>
            <Field label="Target resolution date">
              <input
                className="input"
                value={memo.target_resolution_date}
                disabled={!canEdit}
                onChange={(e) => setMemo({ ...memo, target_resolution_date: e.target.value })}
              />
            </Field>
          </div>

          <Field label="Reviewer note (optional)">
            <input
              className="input"
              value={memo.reviewer_note ?? ""}
              disabled={!canEdit}
              onChange={(e) => setMemo({ ...memo, reviewer_note: e.target.value })}
            />
          </Field>

          {canDecide ? (
            <div className="flex gap-3">
              <button
                className="btn-primary flex items-center gap-2"
                disabled={submitting}
                onClick={() => handleReview("approved")}
              >
                <CheckCircle2 className="w-4 h-4" />
                Approve
              </button>
              <button
                className="btn-danger flex items-center gap-2"
                disabled={submitting}
                onClick={() => handleReview("rejected")}
              >
                <XCircle className="w-4 h-4" />
                Reject
              </button>
            </div>
          ) : (
            <p className="text-xs text-slate-400">
              Your role can {canEdit ? "override the classification above" : "view this record"}
              , but approving or rejecting requires a Quality Reviewer.
            </p>
          )}

          {error && <p className="text-red-600 text-sm">{error}</p>}
        </div>
      ) : (
        <p className="text-slate-500">Memo not yet drafted for this report.</p>
      )}

      <AuditTrail reportId={record.report_id} />
    </div>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="block">
      <span className="block text-sm font-medium text-slate-700 mb-1">{label}</span>
      {children}
    </label>
  );
}

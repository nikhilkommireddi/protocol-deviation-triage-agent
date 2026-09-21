import { AlertTriangle, CheckCircle2, ClipboardList, Compass, FileSearch, ShieldAlert, XCircle } from "lucide-react";
import type { TriageResult } from "../types";

interface ReasoningTraceProps {
  result: TriageResult;
}

export function ReasoningTrace({ result }: ReasoningTraceProps) {
  const { supervisor_plan, adjudication, protocol_findings, history_findings, verification } = result;

  if (!supervisor_plan && !adjudication && !protocol_findings && !history_findings && !verification) {
    return null;
  }

  return (
    <div className="card space-y-4">
      <div className="flex items-center gap-2 text-slate-700">
        <FileSearch className="w-4 h-4" />
        <h3 className="font-medium">How the AI investigated this</h3>
      </div>

      {supervisor_plan && (
        <div className="text-sm flex items-start gap-2">
          <Compass className="w-4 h-4 text-slate-400 shrink-0 mt-0.5" />
          <div>
            <p className="text-slate-700">
              Supervisor plan:{" "}
              <span className="font-mono text-xs">
                protocol={supervisor_plan.run_protocol_investigation ? "run" : "skip"}, history=
                {supervisor_plan.run_site_history ? "run" : "skip"}
              </span>
            </p>
            <p className="text-slate-500 text-xs mt-0.5">{supervisor_plan.reasoning}</p>
          </div>
        </div>
      )}

      {adjudication && (
        <div className="text-sm space-y-2">
          <p className="text-slate-500">
            Classifier's first guess: <span className="font-mono text-slate-700">{adjudication.classifier_category}</span>
          </p>
          {adjudication.overridden ? (
            <div className="rounded-md bg-amber-50 border border-amber-200 px-3 py-2 flex items-start gap-2">
              <AlertTriangle className="w-4 h-4 text-amber-600 shrink-0 mt-0.5" />
              <p className="text-amber-900">
                <span className="font-medium">Overridden to {adjudication.final_category}.</span>{" "}
                {adjudication.override_reason}
              </p>
            </div>
          ) : (
            <div className="rounded-md bg-green-50 border border-green-200 px-3 py-2 flex items-start gap-2">
              <CheckCircle2 className="w-4 h-4 text-green-600 shrink-0 mt-0.5" />
              <p className="text-green-900">Classifier's category confirmed after investigation.</p>
            </div>
          )}
        </div>
      )}

      {protocol_findings && (
        <div className="text-sm border-t border-slate-200 pt-3">
          <p className="font-medium text-slate-700 flex items-center gap-1.5 mb-1">
            <ClipboardList className="w-4 h-4" /> Protocol investigation
          </p>
          {protocol_findings.relevant ? (
            <div className="rounded-md bg-sky-50 border border-sky-200 px-3 py-2">
              <p className="text-sky-900">{protocol_findings.summary}</p>
              {protocol_findings.citation && (
                <p className="text-xs text-sky-700 mt-1 italic">&ldquo;{protocol_findings.citation}&rdquo;</p>
              )}
            </div>
          ) : (
            <p className="text-slate-500">{protocol_findings.summary}</p>
          )}
        </div>
      )}

      {history_findings && (
        <div className="text-sm border-t border-slate-200 pt-3">
          <p className="font-medium text-slate-700 flex items-center gap-1.5 mb-1">
            <ShieldAlert className="w-4 h-4" /> Site history
          </p>
          {history_findings.pattern_detected ? (
            <div className="rounded-md bg-amber-50 border border-amber-200 px-3 py-2">
              <p className="text-amber-900">{history_findings.summary}</p>
            </div>
          ) : (
            <p className="text-slate-500">{history_findings.summary}</p>
          )}
          {history_findings.prior_count >= 0 && (
            <p className="text-xs text-slate-400 mt-1">
              {history_findings.prior_count} prior deviation(s) on file at this site.
            </p>
          )}
        </div>
      )}

      {verification && (
        <div className="text-sm border-t border-slate-200 pt-3 flex items-start gap-2">
          {verification.passes ? (
            <CheckCircle2 className="w-4 h-4 text-green-600 shrink-0 mt-0.5" />
          ) : (
            <XCircle className="w-4 h-4 text-red-600 shrink-0 mt-0.5" />
          )}
          <div>
            <p className="font-medium text-slate-700">
              {verification.passes ? "Verification passed" : "Verification flagged an issue"}
            </p>
            {verification.issues.length > 0 && (
              <ul className="list-disc list-inside text-slate-600 mt-1">
                {verification.issues.map((issue) => (
                  <li key={issue}>{issue}</li>
                ))}
              </ul>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

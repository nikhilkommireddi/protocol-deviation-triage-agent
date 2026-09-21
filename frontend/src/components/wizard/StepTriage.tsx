import { useEffect, useRef, useState } from "react";
import {
  AlertTriangle,
  CheckCircle2,
  ClipboardCheck,
  Compass,
  Download,
  FileSearch,
  FileText,
  Gavel,
  Lightbulb,
  Loader2,
  RotateCcw,
  ShieldAlert,
} from "lucide-react";
import { submitReport } from "../../api";
import { categoryBadgeClass } from "../../lib/badges";
import { generateReportPdf } from "../../lib/pdfReport";
import { ReasoningTrace } from "../ReasoningTrace";
import type { TriageResult } from "../../types";
import type { WizardFields } from "./SubmitWizard";

interface StepTriageProps {
  fields: WizardFields;
  onSubmitted: (result: TriageResult) => void;
  onStartOver: () => void;
}

// Purely a UI affordance -- the real work happens in the single submitReport
// call below. The pipeline (app/graph.py) now runs 6 sequential agents
// (classifier, protocol investigator, site history, adjudication, memo
// drafting, verification) with no incremental progress hooks, so this
// steps through the real agent sequence on a timer while that request is
// in flight, then reconciles with the real result whichever finishes last.
// Tuned against real eval latency (median ~25s, max ~45s) so it spends
// most of its time actually progressing rather than parked on one item.
const CHECKLIST = [
  { label: "Classifying deviation severity...", icon: AlertTriangle },
  { label: "Planning investigation...", icon: Compass },
  { label: "Investigating protocol details...", icon: FileSearch },
  { label: "Reviewing site history...", icon: ShieldAlert },
  { label: "Adjudicating final category...", icon: Gavel },
  { label: "Drafting review memo...", icon: FileText },
  { label: "Verifying findings...", icon: ClipboardCheck },
];

const STEP_INTERVAL_MS = 3200;

const WORKFLOW_STEPS = ["Submitted", "Classified", "CAPA Lookup", "Memo Drafted", "Queued for Review"];

export function StepTriage({ fields, onSubmitted, onStartOver }: StepTriageProps) {
  const [visualStep, setVisualStep] = useState(0);
  const [result, setResult] = useState<TriageResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const startedRef = useRef(false);

  useEffect(() => {
    if (startedRef.current) return;
    startedRef.current = true;

    const interval = setInterval(() => {
      setVisualStep((s) => Math.min(s + 1, CHECKLIST.length - 1));
    }, STEP_INTERVAL_MS);

    submitReport({
      protocol_id: fields.protocolId,
      site_id: fields.siteId,
      subject_id: fields.subjectId,
      deviation_date: fields.deviationDate,
      discovery_date: fields.discoveryDate,
      text: fields.text,
    })
      .then((res) => {
        clearInterval(interval);
        setVisualStep(CHECKLIST.length);
        setResult(res);
        onSubmitted(res);
      })
      .catch((err) => {
        clearInterval(interval);
        setError(err instanceof Error ? err.message : "Triage submission failed.");
      });

    return () => clearInterval(interval);
    // Intentionally runs once on mount -- fields are a snapshot from the
    // review step, not something this component should re-submit on change.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  if (error) {
    return (
      <div className="card space-y-4">
        <p className="text-red-600 text-sm">{error}</p>
        <button className="btn-secondary" onClick={onStartOver}>
          Start over
        </button>
      </div>
    );
  }

  if (!result) {
    return (
      <div className="space-y-4">
        <div className="card py-10 text-center">
          <Loader2 className="w-12 h-12 text-sky-600 animate-spin mx-auto mb-4" />
          <h3 className="text-base font-semibold text-slate-800 mb-1">Running AI triage...</h3>
          <p className="text-sm text-slate-500 max-w-md mx-auto mb-8">
            Our AI is analyzing the report, classifying severity, routing to the appropriate team,
            and generating a CAPA recommendation.
          </p>

          <div className="max-w-sm mx-auto space-y-4 text-left">
            {CHECKLIST.map(({ label, icon: Icon }, i) => {
              const done = i < visualStep;
              const active = i === visualStep;
              return (
                <div key={label} className="flex items-center gap-3">
                  <div
                    className={
                      "flex items-center justify-center w-7 h-7 rounded-full shrink-0 " +
                      (done
                        ? "bg-green-500 text-white"
                        : active
                          ? "border-2 border-sky-600 text-sky-600"
                          : "border border-slate-300 text-slate-300")
                    }
                  >
                    {done ? (
                      <CheckCircle2 className="w-4 h-4" />
                    ) : active ? (
                      <Loader2 className="w-3.5 h-3.5 animate-spin" />
                    ) : (
                      <Icon className="w-3.5 h-3.5" />
                    )}
                  </div>
                  <span className={"text-sm " + (done || active ? "text-slate-800" : "text-slate-400")}>
                    {label}
                  </span>
                </div>
              );
            })}
          </div>
        </div>

        <div className="card flex items-center gap-2 bg-slate-50 justify-center">
          <Lightbulb className="w-4 h-4 text-amber-500 shrink-0" />
          <p className="text-xs text-slate-500">
            This usually takes 20-45 seconds -- six specialized agents review this case in sequence.
          </p>
        </div>
      </div>
    );
  }

  const confidencePct = result.confidence !== null ? Math.round(result.confidence * 100) : null;
  const requiresExpedited = result.memo?.requires_expedited_reporting ?? false;

  return (
    <div className="space-y-6">
      <div className="card space-y-4">
        <div className="flex items-center justify-between">
          <h3 className="font-medium text-slate-800">Triage complete</h3>
          <span className={categoryBadgeClass(result.category)}>{result.category ?? "unclassified"}</span>
        </div>

        <div className="grid grid-cols-2 gap-4">
          <div>
            <p className="text-xs text-slate-500 mb-1">Confidence</p>
            <p className="text-sm font-medium text-slate-800 mb-1">
              {confidencePct !== null ? `${confidencePct}%` : "-"}
            </p>
            <div className="h-1.5 rounded-full bg-slate-100 overflow-hidden">
              <div className="h-full bg-sky-600 rounded-full" style={{ width: `${confidencePct ?? 0}%` }} />
            </div>
          </div>
          <div>
            <p className="text-xs text-slate-500 mb-1">Routing team</p>
            <p className="text-sm font-medium text-slate-800">
              {result.capa_guidance?.routing_team ?? "-"}
            </p>
          </div>
        </div>

        <span className={requiresExpedited ? "badge badge-red" : "badge badge-slate"}>
          {requiresExpedited ? "Expedited reporting required" : "Standard CAPA timeline"}
        </span>
      </div>

      <ReasoningTrace result={result} />

      <div className="card">
        <h3 className="font-medium text-slate-800 mb-4">Workflow</h3>
        <div className="flex items-start">
          {WORKFLOW_STEPS.map((label, i) => (
            <div key={label} className="flex items-center flex-1 last:flex-none">
              <div className="flex flex-col items-center gap-1">
                <div className="step-circle step-circle-done">
                  <CheckCircle2 className="w-4 h-4" />
                </div>
                <span className="text-xs text-slate-600 text-center w-20">{label}</span>
              </div>
              {i < WORKFLOW_STEPS.length - 1 && <div className="flex-1 h-0.5 mx-2 bg-sky-600" />}
            </div>
          ))}
        </div>
      </div>

      <div className="flex gap-3">
        <button className="btn-primary flex items-center gap-2" onClick={() => generateReportPdf(result)}>
          <Download className="w-4 h-4" />
          Download Report
        </button>
        <button className="btn-secondary flex items-center gap-2" onClick={onStartOver}>
          <RotateCcw className="w-4 h-4" />
          Submit another
        </button>
      </div>
    </div>
  );
}

import { useState } from "react";
import { ArrowLeft, ArrowRight, Calendar, CheckCircle2, ClipboardList, FileText } from "lucide-react";
import type { WizardFields } from "./SubmitWizard";

interface StepReviewProps {
  fields: WizardFields;
  onChange: (fields: WizardFields) => void;
  extractedText: string | null;
  onBack: () => void;
  onContinue: () => void;
}

const TEXT_SOFT_LIMIT = 2000;

export function StepReview({ fields, onChange, extractedText, onBack, onContinue }: StepReviewProps) {
  const [showExtracted, setShowExtracted] = useState(false);

  function set<K extends keyof WizardFields>(key: K, value: WizardFields[K]) {
    onChange({ ...fields, [key]: value });
  }

  const canContinue =
    fields.text.trim().length > 0 && !!fields.deviationDate && !!fields.discoveryDate;

  return (
    <div className="space-y-4">
      {extractedText && (
        <div className="card bg-green-50 border-green-200 flex items-start justify-between gap-4 flex-wrap">
          <div className="flex items-start gap-2">
            <CheckCircle2 className="w-5 h-5 text-green-600 shrink-0 mt-0.5" />
            <div>
              <p className="text-sm font-medium text-green-800">Information extracted successfully!</p>
              <p className="text-xs text-green-700">
                We've pre-filled the fields below. Please review and edit if needed.
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={() => setShowExtracted((v) => !v)}
            className="btn-secondary text-xs px-3 py-1.5 shrink-0"
          >
            {showExtracted ? "Hide Extracted Text" : "View Extracted Text"}
          </button>
        </div>
      )}

      {showExtracted && extractedText && (
        <div className="card">
          <p className="text-xs font-medium text-slate-500 mb-2">
            Original text extracted from the PDF (read-only)
          </p>
          <textarea className="input h-28 bg-slate-50" value={extractedText} disabled />
        </div>
      )}

      <div className="card space-y-3">
        <div className="flex items-center gap-2 text-slate-700">
          <ClipboardList className="w-4 h-4" />
          <h3 className="font-medium">Study Information</h3>
        </div>
        <div className="grid grid-cols-3 gap-4">
          <Field label="Protocol ID" required>
            <input
              className="input"
              value={fields.protocolId}
              onChange={(e) => set("protocolId", e.target.value)}
            />
          </Field>
          <Field label="Site ID" required>
            <input className="input" value={fields.siteId} onChange={(e) => set("siteId", e.target.value)} />
          </Field>
          <Field label="Subject ID" required>
            <input
              className="input"
              value={fields.subjectId}
              onChange={(e) => set("subjectId", e.target.value)}
            />
          </Field>
        </div>
      </div>

      <div className="card space-y-3">
        <div className="flex items-center gap-2 text-slate-700">
          <Calendar className="w-4 h-4" />
          <h3 className="font-medium">Event Timeline</h3>
        </div>
        <div className="grid grid-cols-2 gap-4">
          <Field label="Deviation date" required>
            <input
              type="date"
              className="input"
              value={fields.deviationDate}
              onChange={(e) => set("deviationDate", e.target.value)}
            />
          </Field>
          <Field label="Discovery date" required>
            <input
              type="date"
              className="input"
              value={fields.discoveryDate}
              onChange={(e) => set("discoveryDate", e.target.value)}
            />
          </Field>
        </div>
      </div>

      <div className="card space-y-3">
        <div className="flex items-center gap-2 text-slate-700">
          <FileText className="w-4 h-4" />
          <h3 className="font-medium">Deviation Details</h3>
        </div>
        <Field label="Deviation report text" required>
          <textarea className="input h-36" value={fields.text} onChange={(e) => set("text", e.target.value)} />
        </Field>
        <p
          className={
            "text-xs text-right " +
            (fields.text.length > TEXT_SOFT_LIMIT ? "text-amber-600" : "text-slate-400")
          }
        >
          {fields.text.length} / {TEXT_SOFT_LIMIT} characters
        </p>
      </div>

      {!canContinue && (
        <p className="text-xs text-slate-500">
          Deviation report text, deviation date, and discovery date are all required.
        </p>
      )}

      <div className="flex gap-3">
        <button type="button" onClick={onBack} className="btn-secondary flex items-center gap-2">
          <ArrowLeft className="w-4 h-4" />
          Back
        </button>
        <button
          type="button"
          onClick={onContinue}
          disabled={!canContinue}
          className="btn-primary flex items-center gap-2"
        >
          Run AI Triage
          <ArrowRight className="w-4 h-4" />
        </button>
      </div>
    </div>
  );
}

function Field({
  label,
  required,
  children,
}: {
  label: string;
  required?: boolean;
  children: React.ReactNode;
}) {
  return (
    <label className="block">
      <span className="block text-sm font-medium text-slate-700 mb-1">
        {label}
        {required && <span className="text-red-500"> *</span>}
      </span>
      {children}
    </label>
  );
}

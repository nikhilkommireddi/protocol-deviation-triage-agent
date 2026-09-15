import { useState } from "react";
import { Check } from "lucide-react";
import { StepUpload } from "./StepUpload";
import { StepReview } from "./StepReview";
import { StepTriage } from "./StepTriage";
import { PageHeader } from "../PageHeader";
import type { TriageResult } from "../../types";

interface SubmitWizardProps {
  onSubmitted: (result: TriageResult) => void;
}

export interface WizardFields {
  protocolId: string;
  siteId: string;
  subjectId: string;
  deviationDate: string;
  discoveryDate: string;
  text: string;
}

const DEFAULT_FIELDS: WizardFields = {
  protocolId: "PDA-2024-001",
  siteId: "001",
  subjectId: "001-1234",
  deviationDate: "",
  discoveryDate: "",
  text: "",
};

const STEPS = [
  { n: 1, label: "Upload / Enter Report" },
  { n: 2, label: "Review Information" },
  { n: 3, label: "AI Triage" },
] as const;

export function SubmitWizard({ onSubmitted }: SubmitWizardProps) {
  const [step, setStep] = useState<1 | 2 | 3>(1);
  const [fields, setFields] = useState<WizardFields>(DEFAULT_FIELDS);
  const [extractedText, setExtractedText] = useState<string | null>(null);

  function mergeExtracted(extracted: Partial<WizardFields>) {
    // Extraction can leave fields blank (not found in the PDF) -- an empty
    // string shouldn't clobber a value already in the form.
    setFields((prev) => ({
      ...prev,
      ...Object.fromEntries(Object.entries(extracted).filter(([, v]) => !!v)),
    }));
  }

  function resetWizard() {
    setFields(DEFAULT_FIELDS);
    setExtractedText(null);
    setStep(1);
  }

  return (
    <div className={step === 1 ? "max-w-5xl" : "max-w-3xl"}>
      <PageHeader
        title="Protocol Deviation Triage Agent"
        subtitle="AI-powered classification, routing, and CAPA recommendation for protocol deviations"
      />

      <div className="flex items-center mb-8">
        {STEPS.map((s, i) => (
          <div key={s.n} className="flex items-center flex-1 last:flex-none">
            <div className="flex items-center gap-2 whitespace-nowrap">
              <div
                className={
                  "step-circle " +
                  (step > s.n
                    ? "step-circle-done"
                    : step === s.n
                      ? "step-circle-active"
                      : "step-circle-upcoming")
                }
              >
                {step > s.n ? <Check className="w-4 h-4" /> : s.n}
              </div>
              <span
                className={
                  "text-sm font-medium " + (step >= s.n ? "text-slate-700" : "text-slate-400")
                }
              >
                {s.label}
              </span>
            </div>
            {i < STEPS.length - 1 && (
              <div className={"flex-1 h-0.5 mx-3 " + (step > s.n ? "bg-sky-600" : "bg-slate-200")} />
            )}
          </div>
        ))}
      </div>

      {step === 1 && (
        <StepUpload
          onExtracted={(extracted) => {
            mergeExtracted(extracted);
            setExtractedText(extracted.text || null);
            setStep(2);
          }}
          onManual={() => setStep(2)}
        />
      )}

      {step === 2 && (
        <StepReview
          fields={fields}
          onChange={setFields}
          extractedText={extractedText}
          onBack={() => setStep(1)}
          onContinue={() => setStep(3)}
        />
      )}

      {step === 3 && (
        <StepTriage fields={fields} onSubmitted={onSubmitted} onStartOver={resetWizard} />
      )}
    </div>
  );
}

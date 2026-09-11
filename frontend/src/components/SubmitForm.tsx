import { useState } from "react";
import { submitReport } from "../api";
import type { TriageResult } from "../types";

interface SubmitFormProps {
  onSubmitted: (result: TriageResult) => void;
}

export function SubmitForm({ onSubmitted }: SubmitFormProps) {
  const [protocolId, setProtocolId] = useState("PDA-2024-001");
  const [siteId, setSiteId] = useState("001");
  const [subjectId, setSubjectId] = useState("001-1234");
  const [deviationDate, setDeviationDate] = useState("");
  const [discoveryDate, setDiscoveryDate] = useState("");
  const [text, setText] = useState("");

  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setSuccessMessage(null);

    if (!text.trim() || !deviationDate || !discoveryDate) {
      setError("Deviation report text, deviation date, and discovery date are all required.");
      return;
    }

    setSubmitting(true);
    try {
      const result = await submitReport({
        protocol_id: protocolId,
        site_id: siteId,
        subject_id: subjectId,
        deviation_date: deviationDate,
        discovery_date: discoveryDate,
        text,
      });
      setSuccessMessage(
        `Triaged as ${result.category} (confidence ${result.confidence?.toFixed(2)}) and drafted for review. See the Review Queue tab.`,
      );
      onSubmitted(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Submission failed.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="max-w-3xl">
      <h2 className="text-lg font-semibold text-slate-800 mb-4">Submit a deviation report</h2>
      <form onSubmit={handleSubmit} className="space-y-4">
        <div className="grid grid-cols-3 gap-4">
          <Field label="Protocol ID">
            <input
              className="input"
              value={protocolId}
              onChange={(e) => setProtocolId(e.target.value)}
            />
          </Field>
          <Field label="Site ID">
            <input className="input" value={siteId} onChange={(e) => setSiteId(e.target.value)} />
          </Field>
          <Field label="Subject ID">
            <input
              className="input"
              value={subjectId}
              onChange={(e) => setSubjectId(e.target.value)}
            />
          </Field>
        </div>

        <div className="grid grid-cols-2 gap-4">
          <Field label="Deviation date (YYYY-MM-DD)">
            <input
              className="input"
              placeholder="2024-05-01"
              value={deviationDate}
              onChange={(e) => setDeviationDate(e.target.value)}
            />
          </Field>
          <Field label="Discovery date (YYYY-MM-DD)">
            <input
              className="input"
              placeholder="2024-05-02"
              value={discoveryDate}
              onChange={(e) => setDiscoveryDate(e.target.value)}
            />
          </Field>
        </div>

        <Field label="Deviation report text">
          <textarea
            className="input h-36"
            value={text}
            onChange={(e) => setText(e.target.value)}
          />
        </Field>

        <button type="submit" disabled={submitting} className="btn-primary">
          {submitting ? "Running triage pipeline (classify + draft memo)..." : "Submit for triage"}
        </button>

        {error && <p className="text-red-600 text-sm">{error}</p>}
        {successMessage && <p className="text-green-700 text-sm">{successMessage}</p>}
      </form>
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

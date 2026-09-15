import { useRef, useState } from "react";
import { CheckCircle2, FileEdit, FileText, Loader2, ShieldCheck, Upload } from "lucide-react";
import { extractFromPdf } from "../../api";
import type { ExtractedFields } from "../../types";

interface StepUploadProps {
  onExtracted: (fields: ExtractedFields) => void;
  onManual: () => void;
}

const NEXT_STEPS = [
  "We extract key information from your report",
  "You review and edit the fields",
  "Our AI classifies severity, routes to the right team, and generates a CAPA recommendation",
  "You can review and download the full report",
];

export function StepUpload({ onExtracted, onManual }: StepUploadProps) {
  const [dragActive, setDragActive] = useState(false);
  const [extracting, setExtracting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  async function handleFile(file: File) {
    setExtracting(true);
    setError(null);
    try {
      const fields = await extractFromPdf(file);
      onExtracted(fields);
    } catch (err) {
      setError(err instanceof Error ? err.message : "PDF extraction failed.");
    } finally {
      setExtracting(false);
    }
  }

  function handleDrop(e: React.DragEvent<HTMLDivElement>) {
    e.preventDefault();
    setDragActive(false);
    const file = e.dataTransfer.files?.[0];
    if (file) handleFile(file);
  }

  return (
    <div className="grid grid-cols-3 gap-6">
      <div className="col-span-2 space-y-4">
        <div
          onDragOver={(e) => {
            e.preventDefault();
            setDragActive(true);
          }}
          onDragLeave={() => setDragActive(false)}
          onDrop={handleDrop}
          className={
            "card border-2 border-dashed flex flex-col items-center justify-center text-center py-14 gap-3 " +
            (dragActive ? "border-sky-500 bg-sky-50" : "border-slate-300")
          }
        >
          <input
            ref={fileInputRef}
            type="file"
            accept="application/pdf,.pdf"
            className="hidden"
            onChange={(e) => {
              const file = e.target.files?.[0];
              if (file) handleFile(file);
              e.target.value = "";
            }}
          />
          {extracting ? (
            <>
              <Loader2 className="w-10 h-10 text-sky-600 animate-spin" />
              <p className="text-sm font-medium text-slate-700">Extracting data from PDF...</p>
            </>
          ) : (
            <>
              <FileText className="w-10 h-10 text-sky-300" />
              <p className="text-base font-semibold text-slate-800">Upload Protocol Deviation PDF</p>
              <p className="text-sm text-slate-500">
                Drag and drop your PDF here, or{" "}
                <button
                  type="button"
                  onClick={() => fileInputRef.current?.click()}
                  className="text-sky-600 font-medium hover:underline"
                >
                  click to browse
                </button>
              </p>
              <button
                type="button"
                onClick={() => fileInputRef.current?.click()}
                className="btn-primary flex items-center gap-2 mt-2"
              >
                <Upload className="w-4 h-4" />
                Browse Files
              </button>
              <p className="text-xs text-slate-400">Supported format: PDF &bull; Max size: 10 MB</p>
            </>
          )}
        </div>

        {error && <p className="text-red-600 text-sm">{error}</p>}

        <div className="flex items-center gap-3">
          <div className="flex-1 h-px bg-slate-200" />
          <span className="text-xs text-slate-400">OR</span>
          <div className="flex-1 h-px bg-slate-200" />
        </div>

        <button
          type="button"
          onClick={onManual}
          className="btn-secondary w-full flex items-center justify-center gap-2"
        >
          <FileEdit className="w-4 h-4" />
          Enter information manually
        </button>
      </div>

      <div className="space-y-4">
        <div className="card">
          <h3 className="font-medium text-slate-800 mb-4">What happens next?</h3>
          <div className="space-y-4">
            {NEXT_STEPS.map((text) => (
              <div key={text} className="flex items-start gap-3">
                <CheckCircle2 className="w-5 h-5 text-green-500 shrink-0 mt-0.5" />
                <p className="text-sm text-slate-600">{text}</p>
              </div>
            ))}
          </div>
        </div>

        <div className="card flex items-start gap-2 bg-slate-50">
          <ShieldCheck className="w-4 h-4 text-slate-400 shrink-0 mt-0.5" />
          <p className="text-xs text-slate-500">
            Your data is secure and used only for clinical operations.
          </p>
        </div>
      </div>
    </div>
  );
}

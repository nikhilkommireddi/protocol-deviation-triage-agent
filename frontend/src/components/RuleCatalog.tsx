import { useEffect, useState } from "react";
import { Users } from "lucide-react";
import { getReferenceData } from "../api";
import type { ReferenceData } from "../types";
import { categoryBadgeClass } from "../lib/badges";
import { renderMiniMarkdown } from "../lib/miniMarkdown";
import { PageHeader } from "./PageHeader";

export function RuleCatalog() {
  const [data, setData] = useState<ReferenceData | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getReferenceData()
      .then(setData)
      .catch((err) => setError(err instanceof Error ? err.message : "Failed to load reference data."));
  }, []);

  if (error) return <p className="text-red-600">{error}</p>;
  if (!data) return <p className="text-slate-500">Loading...</p>;

  return (
    <div>
      <PageHeader
        title="Rule Catalog"
        subtitle="The category definitions and CAPA requirements the Adjudication Agent reasons against"
      />

      <div className="grid grid-cols-2 gap-4 mb-8">
        {Object.entries(data.capa_guidance).map(([category, guidance]) => (
          <div key={category} className="card">
            <div className="flex items-center justify-between mb-2">
              <span className={categoryBadgeClass(category)}>{category}</span>
            </div>
            <p className="text-sm text-slate-700 mb-1">
              <span className="font-medium">Routing team:</span> {guidance.routing_team}
            </p>
            <p className="text-xs text-slate-500 mb-2">{guidance.regulatory_reference}</p>
            <div className="flex items-center gap-1.5 text-xs font-medium text-slate-500 mb-1">
              <Users className="w-3.5 h-3.5" />
              Required CAPA elements
            </div>
            <ul className="list-disc list-inside text-sm text-slate-700 space-y-0.5">
              {guidance.required_capa_elements.map((el) => (
                <li key={el}>{el}</li>
              ))}
            </ul>
          </div>
        ))}
      </div>

      <div className="card">{renderMiniMarkdown(data.labels_markdown)}</div>
    </div>
  );
}

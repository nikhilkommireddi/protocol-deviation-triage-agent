import { useEffect, useMemo, useState } from "react";
import { Check, Info, MapPin, Minus, Users } from "lucide-react";
import { listReports } from "../api";
import type { TriageResult } from "../types";
import {
  ALL_ROLES,
  CAPABILITY_LABELS,
  ROLE_CAPABILITIES,
  ROLE_INFO,
  can,
  type Capability,
} from "../lib/permissions";
import { PageHeader } from "./PageHeader";
import { StatCard } from "./StatCard";

export function Administration() {
  const [reports, setReports] = useState<TriageResult[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    listReports()
      .then(setReports)
      .catch((err) => setError(err instanceof Error ? err.message : "Failed to load reports."))
      .finally(() => setLoading(false));
  }, []);

  const capabilityKeys = useMemo(() => {
    const keys = new Set<Capability>();
    for (const role of ALL_ROLES) {
      for (const cap of ROLE_CAPABILITIES[role]) keys.add(cap);
    }
    return Array.from(keys);
  }, []);

  const sites = useMemo(() => new Set(reports.map((r) => r.site_id)), [reports]);

  return (
    <div>
      <PageHeader
        title="Administration"
        subtitle="Role permissions and system-wide oversight"
      />

      <div className="card bg-amber-50 border-amber-200 flex items-start gap-2 mb-6">
        <Info className="w-4 h-4 text-amber-600 shrink-0 mt-0.5" />
        <p className="text-sm text-amber-900">
          This is a read-only view. There's no backend user/site management to connect to yet,
          so this page shows the actual permission configuration driving navigation access
          rather than a form that would save nowhere real.
        </p>
      </div>

      {loading ? (
        <p className="text-slate-500">Loading...</p>
      ) : error ? (
        <p className="text-red-600">{error}</p>
      ) : (
        <div className="grid grid-cols-3 gap-4 mb-6">
          <StatCard
            icon={<Users className="w-5 h-5" />}
            label="Total reports"
            value={reports.length}
            accent="bg-slate-100 text-slate-600"
          />
          <StatCard
            icon={<MapPin className="w-5 h-5" />}
            label="Sites represented"
            value={sites.size}
            accent="bg-sky-50 text-sky-600"
          />
          <StatCard
            icon={<Users className="w-5 h-5" />}
            label="Roles configured"
            value={ALL_ROLES.length}
            accent="bg-violet-50 text-violet-600"
          />
        </div>
      )}

      <div className="card overflow-x-auto">
        <h3 className="font-medium text-slate-800 mb-3">Role permission matrix</h3>
        <table className="min-w-full text-sm">
          <thead>
            <tr className="text-left text-slate-500 border-b border-slate-200">
              <th className="py-2 pr-4">Capability</th>
              {ALL_ROLES.map((role) => (
                <th key={role} className="py-2 px-3 text-center">
                  {ROLE_INFO.find((r) => r.role === role)?.title}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {capabilityKeys.map((cap) => (
              <tr key={cap} className="border-b border-slate-100">
                <td className="py-2 pr-4 text-slate-700">{CAPABILITY_LABELS[cap]}</td>
                {ALL_ROLES.map((role) => (
                  <td key={role} className="py-2 px-3 text-center">
                    {can({ name: "", role, siteId: undefined }, cap) ? (
                      <Check className="w-4 h-4 text-green-600 inline" />
                    ) : (
                      <Minus className="w-4 h-4 text-slate-300 inline" />
                    )}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

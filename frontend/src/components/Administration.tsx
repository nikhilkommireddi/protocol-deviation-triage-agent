import { useEffect, useMemo, useState } from "react";
import { Check, MapPin, Minus, Shield, UserCog, Users } from "lucide-react";
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
import { UsersPanel } from "./admin/UsersPanel";
import { SitesPanel } from "./admin/SitesPanel";

type Tab = "overview" | "users" | "sites";

export function Administration() {
  const [tab, setTab] = useState<Tab>("overview");

  return (
    <div>
      <PageHeader title="Administration" subtitle="Users, sites, and role permissions" />

      <div className="flex gap-1 mb-6 border-b border-slate-200">
        <TabButton active={tab === "overview"} icon={<Shield className="w-4 h-4" />} onClick={() => setTab("overview")}>
          Overview
        </TabButton>
        <TabButton active={tab === "users"} icon={<UserCog className="w-4 h-4" />} onClick={() => setTab("users")}>
          Users
        </TabButton>
        <TabButton active={tab === "sites"} icon={<MapPin className="w-4 h-4" />} onClick={() => setTab("sites")}>
          Sites
        </TabButton>
      </div>

      {tab === "overview" && <Overview />}
      {tab === "users" && <UsersPanel />}
      {tab === "sites" && <SitesPanel />}
    </div>
  );
}

function TabButton({
  active,
  icon,
  onClick,
  children,
}: {
  active: boolean;
  icon: React.ReactNode;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      onClick={onClick}
      className={
        "flex items-center gap-2 px-4 py-2 text-sm font-medium border-b-2 -mb-px " +
        (active ? "border-sky-600 text-sky-700" : "border-transparent text-slate-500 hover:text-slate-700")
      }
    >
      {icon}
      {children}
    </button>
  );
}

function Overview() {
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

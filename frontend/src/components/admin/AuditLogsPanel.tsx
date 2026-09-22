import { useEffect, useState } from "react";
import { getAllAuditEvents } from "../../api";
import type { AuditEvent } from "../../types";

export function AuditLogsPanel() {
  const [events, setEvents] = useState<AuditEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getAllAuditEvents()
      .then((data) => setEvents([...data].reverse()))
      .catch((err) => setError(err instanceof Error ? err.message : "Failed to load audit logs."))
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <p className="text-slate-500">Loading...</p>;
  if (error) return <p className="text-red-600">{error}</p>;

  return (
    <div className="card overflow-x-auto">
      <h3 className="font-medium text-slate-800 mb-3">Audit logs (all deviations)</h3>
      {events.length === 0 ? (
        <p className="text-sm text-slate-500">No audit events on file yet.</p>
      ) : (
        <table className="min-w-full text-sm">
          <thead>
            <tr className="text-left text-slate-500 border-b border-slate-200">
              <th className="py-2 pr-4">Event Type</th>
              <th className="py-2 pr-4">Description</th>
              <th className="py-2 pr-4">Report ID</th>
              <th className="py-2 pr-4">Actor</th>
              <th className="py-2 pr-4">Created At</th>
            </tr>
          </thead>
          <tbody>
            {events.map((e) => (
              <tr key={e.event_id} className="border-b border-slate-100">
                <td className="py-2 pr-4 text-xs text-slate-600">{e.event_type}</td>
                <td className="py-2 pr-4">{e.description}</td>
                <td className="py-2 pr-4 font-mono text-xs">{e.report_id.slice(0, 8)}</td>
                <td className="py-2 pr-4 text-xs text-slate-500">
                  {e.actor_name ? `${e.actor_name}${e.actor_role ? ` (${e.actor_role})` : ""}` : "-"}
                </td>
                <td className="py-2 pr-4 text-xs text-slate-500">{e.created_at}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}

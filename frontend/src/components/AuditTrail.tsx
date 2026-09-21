import { useEffect, useState } from "react";
import { Bot, CheckSquare, History, Inbox, Send, User } from "lucide-react";
import { getAuditTrail } from "../api";
import type { AuditEvent } from "../types";

interface AuditTrailProps {
  reportId: string;
}

const AI_EVENT_TYPES = new Set(["ai_classified", "ai_adjudicated", "ai_verified"]);

function iconFor(eventType: string) {
  if (eventType === "submitted") return Send;
  if (eventType === "queued") return Inbox;
  if (eventType === "capa_updated") return CheckSquare;
  if (AI_EVENT_TYPES.has(eventType)) return Bot;
  return User;
}

function formatTimestamp(createdAt: string): string {
  const date = new Date(createdAt);
  if (Number.isNaN(date.getTime())) return createdAt;
  return date.toLocaleString();
}

export function AuditTrail({ reportId }: AuditTrailProps) {
  const [events, setEvents] = useState<AuditEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    getAuditTrail(reportId)
      .then((rows) => {
        if (!cancelled) setEvents(rows);
      })
      .catch((err) => {
        if (!cancelled) setError(err instanceof Error ? err.message : "Failed to load audit trail.");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [reportId]);

  return (
    <div className="border-t border-slate-200 pt-4">
      <h3 className="font-medium text-slate-800 mb-3 flex items-center gap-2">
        <History className="w-4 h-4 text-slate-400" />
        Audit trail
      </h3>
      {loading && <p className="text-sm text-slate-500">Loading audit trail...</p>}
      {error && <p className="text-sm text-red-600">{error}</p>}
      {!loading && !error && events.length === 0 && (
        <p className="text-sm text-slate-500">No audit events yet.</p>
      )}
      {!loading && events.length > 0 && (
        <ol className="space-y-3">
          {events.map((event) => {
            const Icon = iconFor(event.event_type);
            return (
              <li key={event.event_id} className="flex items-start gap-3">
                <span className="mt-0.5 shrink-0 rounded-full bg-slate-100 p-1.5 text-slate-500">
                  <Icon className="w-3.5 h-3.5" />
                </span>
                <div className="text-sm">
                  <p className="text-slate-800">{event.description}</p>
                  <p className="text-xs text-slate-500">
                    {formatTimestamp(event.created_at)}
                    {event.actor_name && ` -- ${event.actor_name}`}
                    {event.actor_role && ` (${event.actor_role})`}
                  </p>
                </div>
              </li>
            );
          })}
        </ol>
      )}
    </div>
  );
}

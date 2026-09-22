import { useEffect, useState } from "react";
import { ClipboardList, Inbox, ShieldCheck, ShieldQuestion, UserCog } from "lucide-react";
import { listUsers } from "../api";
import { useAuth } from "../context/AuthContext";
import { ROLE_INFO } from "../lib/permissions";
import type { ManagedUser, UserRole } from "../types";

const ROLE_ICONS: Record<UserRole, React.ReactNode> = {
  site_coordinator: <Inbox className="w-6 h-6" />,
  cra: <ClipboardList className="w-6 h-6" />,
  quality_reviewer: <ShieldCheck className="w-6 h-6" />,
  administrator: <UserCog className="w-6 h-6" />,
};

export function Login() {
  const { login } = useAuth();
  const [users, setUsers] = useState<ManagedUser[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    listUsers()
      .then(setUsers)
      .catch((err) => setError(err instanceof Error ? err.message : "Failed to load users."));
  }, []);

  return (
    <div className="min-h-screen bg-slate-50 flex">
      <div className="hidden lg:flex flex-col justify-between w-[36%] shrink-0 bg-slate-900 text-white px-10 py-12">
        <div className="flex items-center gap-2">
          <ShieldCheck className="w-6 h-6 text-sky-400" />
          <span className="font-semibold">Deviation Triage</span>
        </div>
        <div>
          <h1 className="text-3xl font-bold leading-tight mb-4">
            Ensuring Compliance.
            <br />
            Improving Patient Safety.
          </h1>
          <p className="text-sm text-slate-400 max-w-sm">
            AI-powered insights. Human-driven oversight.
          </p>
        </div>
        <p className="text-xs text-slate-500">Protocol Deviation Triage Agent</p>
      </div>

      <div className="flex-1 flex items-center justify-center px-6 py-12">
        <div className="max-w-2xl w-full">
          <div className="mb-8">
            <h2 className="text-xl font-bold text-slate-900 mb-2">Sign in to your account</h2>
            <p className="text-sm text-slate-500 max-w-lg">
              Pick a user to log in as. This is a frontend-only mock login for demonstration
              purposes -- there is no password check behind it, and every API endpoint remains
              open regardless of which user you pick. The users themselves are real, persisted
              records, managed from the Administration page.
            </p>
            <span className="inline-flex items-center gap-1.5 mt-3 badge badge-amber">
              <ShieldQuestion className="w-3.5 h-3.5" />
              Demo Mode -- not production authentication
            </span>
          </div>

          {error && <p className="text-red-600 text-sm mb-4">{error}</p>}
          {!users && !error && <p className="text-slate-500">Loading users...</p>}

          {users && (
            <div className="grid grid-cols-2 gap-4">
              {ROLE_INFO.map((info) => {
                const roleUsers = users.filter((u) => u.role === info.role);
                return (
                  <div key={info.role} className="card">
                    <div className="flex items-center gap-3 mb-2">
                      <div className="flex items-center justify-center w-10 h-10 rounded-lg bg-sky-50 text-sky-600">
                        {ROLE_ICONS[info.role]}
                      </div>
                      <h2 className="font-semibold text-slate-900">{info.title}</h2>
                    </div>
                    <p className="text-sm text-slate-500 mb-3">{info.description}</p>
                    <ul className="space-y-1 mb-4">
                      {info.capabilities.map((cap) => (
                        <li key={cap} className="text-xs text-slate-600 flex items-start gap-1.5">
                          <span className="text-sky-500 mt-0.5">&bull;</span>
                          {cap}
                        </li>
                      ))}
                    </ul>

                    {roleUsers.length === 0 ? (
                      <p className="text-xs text-slate-400">No users with this role yet.</p>
                    ) : (
                      <div className="space-y-1.5 border-t border-slate-100 pt-3">
                        {roleUsers.map((u) => (
                          <button
                            key={u.user_id}
                            onClick={() => login(u)}
                            className="btn-secondary w-full text-left text-sm flex items-center justify-between"
                          >
                            <span>{u.name}</span>
                            {u.site_id && (
                              <span className="text-xs text-slate-400">Site {u.site_id}</span>
                            )}
                          </button>
                        ))}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

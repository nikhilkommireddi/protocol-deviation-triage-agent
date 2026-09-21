import { ClipboardList, Inbox, ShieldCheck, ShieldQuestion, UserCog } from "lucide-react";
import { useAuth } from "../context/AuthContext";
import { ROLE_INFO } from "../lib/permissions";
import type { UserRole } from "../types";

const ROLE_ICONS: Record<UserRole, React.ReactNode> = {
  site_coordinator: <Inbox className="w-6 h-6" />,
  cra: <ClipboardList className="w-6 h-6" />,
  quality_reviewer: <ShieldCheck className="w-6 h-6" />,
  administrator: <UserCog className="w-6 h-6" />,
};

export function Login() {
  const { login } = useAuth();

  return (
    <div className="min-h-screen bg-slate-50 flex items-center justify-center px-6 py-12">
      <div className="max-w-3xl w-full">
        <div className="text-center mb-8">
          <h1 className="text-2xl font-bold text-slate-900 mb-2">Deviation Triage</h1>
          <p className="text-sm text-slate-500 max-w-lg mx-auto">
            Select a role to explore the demo. This is a frontend-only mock login for
            demonstration purposes -- there is no real authentication behind it, and every API
            endpoint remains open regardless of which role you pick.
          </p>
          <span className="inline-flex items-center gap-1.5 mt-3 badge badge-amber">
            <ShieldQuestion className="w-3.5 h-3.5" />
            Demo Mode -- not production authentication
          </span>
        </div>

        <div className="grid grid-cols-2 gap-4">
          {ROLE_INFO.map((info) => (
            <button
              key={info.role}
              onClick={() => login(info.role)}
              className="card text-left hover:border-sky-300 hover:shadow-md transition-shadow"
            >
              <div className="flex items-center gap-3 mb-2">
                <div className="flex items-center justify-center w-10 h-10 rounded-lg bg-sky-50 text-sky-600">
                  {ROLE_ICONS[info.role]}
                </div>
                <h2 className="font-semibold text-slate-900">{info.title}</h2>
              </div>
              <p className="text-sm text-slate-500 mb-3">{info.description}</p>
              <ul className="space-y-1">
                {info.capabilities.map((cap) => (
                  <li key={cap} className="text-xs text-slate-600 flex items-start gap-1.5">
                    <span className="text-sky-500 mt-0.5">&bull;</span>
                    {cap}
                  </li>
                ))}
              </ul>
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}

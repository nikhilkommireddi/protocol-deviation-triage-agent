import {
  BarChart3,
  BookOpen,
  ClipboardList,
  Inbox,
  LayoutDashboard,
  ShieldAlert,
  ShieldCheck,
  UserCircle,
  UserCog,
  Users,
  Wrench,
} from "lucide-react";
import { useAuth } from "../context/AuthContext";
import { can } from "../lib/permissions";

export type View =
  | "dashboard"
  | "submit"
  | "review"
  | "correct"
  | "analytics"
  | "safety"
  | "rules"
  | "subjects"
  | "admin";

interface SidebarProps {
  active: View;
  onNavigate: (view: View) => void;
}

export function Sidebar({ active, onNavigate }: SidebarProps) {
  const { user, logout } = useAuth();

  return (
    <aside className="sidebar w-64 shrink-0 flex flex-col h-screen sticky top-0">
      <div className="flex items-center gap-2 px-5 py-5 border-b border-white/10">
        <ShieldCheck className="w-6 h-6 text-sky-400" />
        <div>
          <p className="text-sm font-semibold text-slate-100 leading-tight">Deviation Triage</p>
          <p className="text-xs text-slate-500 leading-tight">Clinical trial review</p>
        </div>
      </div>

      <nav className="flex-1 px-3 py-2 space-y-1 overflow-y-auto">
        {can(user, "dashboard") && (
          <NavItem
            icon={<LayoutDashboard className="w-4 h-4" />}
            label="Dashboard"
            active={active === "dashboard"}
            onClick={() => onNavigate("dashboard")}
          />
        )}

        {(can(user, "intake") || can(user, "review") || can(user, "correct")) && (
          <p className="sidebar-group-label">Workflow</p>
        )}
        {can(user, "intake") && (
          <NavItem
            icon={<Inbox className="w-4 h-4" />}
            label="Intake"
            active={active === "submit"}
            onClick={() => onNavigate("submit")}
          />
        )}
        {can(user, "review") && (
          <NavItem
            icon={<ClipboardList className="w-4 h-4" />}
            label="Review"
            active={active === "review"}
            onClick={() => onNavigate("review")}
          />
        )}
        {can(user, "correct") && (
          <NavItem
            icon={<Wrench className="w-4 h-4" />}
            label="Correct"
            active={active === "correct"}
            onClick={() => onNavigate("correct")}
          />
        )}

        {(can(user, "analytics") || can(user, "safety")) && (
          <p className="sidebar-group-label">Oversight</p>
        )}
        {can(user, "analytics") && (
          <NavItem
            icon={<BarChart3 className="w-4 h-4" />}
            label="Analytics"
            active={active === "analytics"}
            onClick={() => onNavigate("analytics")}
          />
        )}
        {can(user, "safety") && (
          <NavItem
            icon={<ShieldAlert className="w-4 h-4" />}
            label="Safety Tracker"
            active={active === "safety"}
            onClick={() => onNavigate("safety")}
          />
        )}

        {(can(user, "rules") || can(user, "subjects")) && (
          <p className="sidebar-group-label">Reference</p>
        )}
        {can(user, "rules") && (
          <NavItem
            icon={<BookOpen className="w-4 h-4" />}
            label="Rule Catalog"
            active={active === "rules"}
            onClick={() => onNavigate("rules")}
          />
        )}
        {can(user, "subjects") && (
          <NavItem
            icon={<Users className="w-4 h-4" />}
            label="Subjects"
            active={active === "subjects"}
            onClick={() => onNavigate("subjects")}
          />
        )}

        {can(user, "admin") && (
          <>
            <p className="sidebar-group-label">Administration</p>
            <NavItem
              icon={<UserCog className="w-4 h-4" />}
              label="Administration"
              active={active === "admin"}
              onClick={() => onNavigate("admin")}
            />
          </>
        )}
      </nav>

      <div className="border-t border-white/10 px-5 py-4">
        <div className="flex items-center gap-2 mb-2">
          <UserCircle className="w-7 h-7 text-slate-500" />
          <div>
            <p className="text-sm font-medium text-slate-200 leading-tight">
              {user?.name ?? "Reviewer"}
            </p>
            <p className="text-xs text-slate-500 leading-tight">
              {user?.siteId ? `Site ${user.siteId}` : "Demo session"}
            </p>
          </div>
        </div>
        <button
          type="button"
          onClick={logout}
          className="text-xs text-slate-500 hover:text-slate-300 pl-9"
        >
          Sign out
        </button>
      </div>
    </aside>
  );
}

function NavItem({
  icon,
  label,
  active,
  disabled,
  onClick,
}: {
  icon: React.ReactNode;
  label: string;
  active?: boolean;
  disabled?: boolean;
  onClick?: () => void;
}) {
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      className={
        "sidebar-link " +
        (disabled
          ? "sidebar-link-disabled"
          : active
            ? "sidebar-link-active"
            : "sidebar-link-inactive")
      }
    >
      {icon}
      <span className="flex-1">{label}</span>
      {disabled && (
        <span className="text-[10px] uppercase tracking-wide text-slate-400 border border-slate-200 rounded px-1.5 py-0.5">
          Soon
        </span>
      )}
    </button>
  );
}

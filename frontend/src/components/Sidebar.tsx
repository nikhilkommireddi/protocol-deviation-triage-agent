import { BarChart3, ClipboardList, FileText, ShieldCheck, UserCircle } from "lucide-react";

export type View = "submit" | "review" | "analytics";

interface SidebarProps {
  active: View;
  onNavigate: (view: View) => void;
}

export function Sidebar({ active, onNavigate }: SidebarProps) {
  return (
    <aside className="w-64 shrink-0 border-r border-slate-200 bg-white flex flex-col h-screen sticky top-0">
      <div className="flex items-center gap-2 px-5 py-5 border-b border-slate-200">
        <ShieldCheck className="w-6 h-6 text-sky-600" />
        <div>
          <p className="text-sm font-semibold text-slate-900 leading-tight">Deviation Triage</p>
          <p className="text-xs text-slate-500 leading-tight">Clinical trial review</p>
        </div>
      </div>

      <nav className="flex-1 px-3 py-4 space-y-1">
        <NavItem
          icon={<FileText className="w-4 h-4" />}
          label="Submit New Deviation"
          active={active === "submit"}
          onClick={() => onNavigate("submit")}
        />
        <NavItem
          icon={<ClipboardList className="w-4 h-4" />}
          label="Review Queue"
          active={active === "review"}
          onClick={() => onNavigate("review")}
        />
        <NavItem
          icon={<BarChart3 className="w-4 h-4" />}
          label="Analytics"
          active={active === "analytics"}
          onClick={() => onNavigate("analytics")}
        />
      </nav>

      <div className="border-t border-slate-200 px-5 py-4">
        <div className="flex items-center gap-2 mb-2">
          <UserCircle className="w-7 h-7 text-slate-400" />
          <div>
            <p className="text-sm font-medium text-slate-700 leading-tight">Reviewer</p>
            <p className="text-xs text-slate-500 leading-tight">Demo session</p>
          </div>
        </div>
        <button type="button" className="text-xs text-slate-400 hover:text-slate-600 pl-9">
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

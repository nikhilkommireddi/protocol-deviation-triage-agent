import { HelpCircle } from "lucide-react";

interface PageHeaderProps {
  title: string;
  subtitle?: string;
}

export function PageHeader({ title, subtitle }: PageHeaderProps) {
  return (
    <div className="flex items-start justify-between mb-6">
      <div>
        <h1 className="text-2xl font-bold text-slate-900">{title}</h1>
        {subtitle && <p className="text-sm text-slate-500 mt-1">{subtitle}</p>}
      </div>
      <button
        type="button"
        className="flex items-center gap-1.5 text-sm text-slate-500 hover:text-slate-700 shrink-0"
      >
        <HelpCircle className="w-4 h-4" />
        Help
      </button>
    </div>
  );
}

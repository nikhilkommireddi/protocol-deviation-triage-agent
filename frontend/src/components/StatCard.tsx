interface StatCardProps {
  icon: React.ReactNode;
  label: string;
  value: number | string;
  accent?: string;
}

export function StatCard({ icon, label, value, accent = "bg-sky-50 text-sky-600" }: StatCardProps) {
  return (
    <div className="stat-card">
      <div className={`flex items-center justify-center w-10 h-10 rounded-lg ${accent}`}>{icon}</div>
      <div>
        <p className="text-xs text-slate-500">{label}</p>
        <p className="text-xl font-semibold text-slate-900">{value}</p>
      </div>
    </div>
  );
}

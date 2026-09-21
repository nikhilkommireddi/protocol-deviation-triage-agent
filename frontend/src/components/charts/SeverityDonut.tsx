import { CATEGORY_COLOR } from "../../lib/badges";

interface SeverityDonutProps {
  data: { category: string; count: number }[];
  total: number;
}

export function SeverityDonut({ data, total }: SeverityDonutProps) {
  const radius = 40;
  const circumference = 2 * Math.PI * radius;
  let offset = 0;

  return (
    <div className="flex items-center gap-4">
      <svg viewBox="0 0 100 100" className="w-28 h-28 shrink-0 -rotate-90">
        <circle cx="50" cy="50" r={radius} fill="none" stroke="#e2e8f0" strokeWidth={14} />
        {data.map(({ category, count }) => {
          const fraction = count / total;
          const dash = fraction * circumference;
          const circle = (
            <circle
              key={category}
              cx="50"
              cy="50"
              r={radius}
              fill="none"
              stroke={CATEGORY_COLOR[category] ?? "#94a3b8"}
              strokeWidth={14}
              strokeDasharray={`${dash} ${circumference - dash}`}
              strokeDashoffset={-offset}
            />
          );
          offset += dash;
          return circle;
        })}
      </svg>
      <div className="space-y-1.5">
        {data.map(({ category, count }) => (
          <div key={category} className="flex items-center gap-2 text-xs">
            <span
              className="w-2.5 h-2.5 rounded-full shrink-0"
              style={{ backgroundColor: CATEGORY_COLOR[category] ?? "#94a3b8" }}
            />
            <span className="capitalize text-slate-700">{category}</span>
            <span className="text-slate-400">({count})</span>
          </div>
        ))}
      </div>
    </div>
  );
}

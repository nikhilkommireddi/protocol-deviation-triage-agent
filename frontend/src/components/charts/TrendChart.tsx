interface TrendChartProps {
  data: { label: string; count: number }[];
}

export function TrendChart({ data }: TrendChartProps) {
  const width = 480;
  const height = 140;
  const padding = 24;
  const max = Math.max(1, ...data.map((d) => d.count));
  const stepX = (width - padding * 2) / Math.max(1, data.length - 1);

  const points = data.map((d, i) => {
    const x = padding + i * stepX;
    const y = height - padding - (d.count / max) * (height - padding * 2);
    return { x, y, ...d };
  });

  const path = points.map((p, i) => `${i === 0 ? "M" : "L"}${p.x},${p.y}`).join(" ");

  return (
    <svg viewBox={`0 0 ${width} ${height}`} className="w-full h-36">
      <path d={path} fill="none" stroke="#0284c7" strokeWidth={2} />
      {points.map((p) => (
        <circle key={p.label + p.x} cx={p.x} cy={p.y} r={3} fill="#0284c7" />
      ))}
      {points.map((p) => (
        <text key={`label-${p.label}-${p.x}`} x={p.x} y={height - 4} fontSize={10} fill="#64748b" textAnchor="middle">
          {p.label}
        </text>
      ))}
    </svg>
  );
}

import { useId } from 'react';

export interface ChartPoint {
  time: number;
  value: number;
}

export function Sparkline({
  points,
  color = '#83c9e5',
  height = 64,
  label,
  domain,
}: {
  points: ChartPoint[];
  color?: string;
  height?: number;
  label: string;
  domain?: [number, number];
}) {
  const id = useId().replaceAll(':', '');
  if (points.length < 2)
    return (
      <div className="chart-empty" style={{ height }}>
        Collecting measured history
      </div>
    );
  const width = 600;
  const minimum = domain?.[0] ?? Math.min(...points.map((p) => p.value)) * 0.92;
  const maximum = domain?.[1] ?? Math.max(...points.map((p) => p.value)) * 1.08;
  const span = Math.max(maximum - minimum, 1);
  const first = points[0].time;
  const last = points[points.length - 1].time;
  const coordinates = points.map((point) => [
    ((point.time - first) / Math.max(1, last - first)) * width,
    height - 4 - ((point.value - minimum) / span) * (height - 8),
  ]);
  const path = coordinates
    .map(([x, y], i) => `${i ? 'L' : 'M'}${x.toFixed(2)},${y.toFixed(2)}`)
    .join(' ');
  return (
    <svg
      viewBox={`0 0 ${width} ${height}`}
      preserveAspectRatio="none"
      className="sparkline"
      role="img"
      aria-label={label}
      style={{ height }}
    >
      <defs>
        <linearGradient id={id} x1="0" x2="0" y1="0" y2="1">
          <stop stopColor={color} stopOpacity="0.17" />
          <stop offset="1" stopColor={color} stopOpacity="0" />
        </linearGradient>
      </defs>
      {[0.25, 0.5, 0.75].map((y) => (
        <line
          key={y}
          x1="0"
          x2={width}
          y1={height * y}
          y2={height * y}
          stroke="#293342"
          strokeWidth="0.7"
          strokeDasharray="3 5"
        />
      ))}
      <path d={`${path} L${width},${height} L0,${height} Z`} fill={`url(#${id})`} />
      <path
        d={path}
        fill="none"
        stroke={color}
        strokeWidth="1.6"
        vectorEffect="non-scaling-stroke"
      />
    </svg>
  );
}

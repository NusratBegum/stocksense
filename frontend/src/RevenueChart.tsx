import { useState } from 'react';
import { shortDay, thb } from './format';

type Day = { day: string; revenue: string };

/* Daily revenue as bars: one series, so no legend; the heading names it. */
export default function RevenueChart({ data }: { data: Day[] }) {
  const [hover, setHover] = useState<number | null>(null);
  const W = 720;
  const H = 220;
  const pad = { top: 12, right: 8, bottom: 24, left: 56 };
  const values = data.map((d) => Number(d.revenue));
  const max = Math.max(1, ...values);
  const step = niceStep(max);
  const top = Math.ceil(max / step) * step;
  const innerW = W - pad.left - pad.right;
  const innerH = H - pad.top - pad.bottom;
  const slot = innerW / data.length;
  const barW = Math.max(2, slot - 2);
  const y = (v: number) => pad.top + innerH - (v / top) * innerH;
  const ticks = Array.from({ length: Math.round(top / step) + 1 }, (_, i) => i * step);
  const labelEvery = Math.ceil(data.length / 6);
  const active = hover === null ? null : data[hover];

  return (
    <div className="chart">
      <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label="Daily revenue bar chart" onMouseLeave={() => setHover(null)}>
        {ticks.map((t) => (
          <g key={t}>
            <line x1={pad.left} x2={W - pad.right} y1={y(t)} y2={y(t)} className="grid" />
            <text x={pad.left - 8} y={y(t)} className="axis" textAnchor="end" dominantBaseline="middle">
              {t >= 1000 ? `${t / 1000}k` : t}
            </text>
          </g>
        ))}
        {data.map((d, i) => {
          const v = values[i];
          const x = pad.left + i * slot + 1;
          const h = Math.max(v > 0 ? 2 : 0, pad.top + innerH - y(v));
          return (
            <g key={d.day} onMouseEnter={() => setHover(i)}>
              <rect x={pad.left + i * slot} y={pad.top} width={slot} height={innerH} fill="transparent" />
              <path d={roundedTop(x, pad.top + innerH - h, barW, h)} className={hover === i ? 'bar bar-hot' : 'bar'} />
              {i % labelEvery === 0 && (
                <text x={x + barW / 2} y={H - 6} className="axis" textAnchor="middle">
                  {shortDay(d.day)}
                </text>
              )}
            </g>
          );
        })}
      </svg>
      {active && hover !== null && (
        <div className="tooltip" style={{ left: `${((pad.left + (hover + 0.5) * slot) / W) * 100}%` }}>
          <strong>{thb(active.revenue)}</strong>
          <span>{shortDay(active.day)}</span>
        </div>
      )}
    </div>
  );
}

function niceStep(max: number) {
  const raw = max / 4;
  const mag = 10 ** Math.floor(Math.log10(raw));
  return [1, 2, 2.5, 5, 10].map((m) => m * mag).find((s) => s >= raw) ?? raw;
}

function roundedTop(x: number, y: number, w: number, h: number) {
  const r = Math.min(4, w / 2, h);
  return `M${x},${y + h} V${y + r} Q${x},${y} ${x + r},${y} H${x + w - r} Q${x + w},${y} ${x + w},${y + r} V${y + h} Z`;
}

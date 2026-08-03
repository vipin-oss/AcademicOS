"use client";

import type { ReportChart } from "@/types";

/**
 * Dependency-free SVG charts (PART 10 — "lightweight charting already
 * compatible with the existing frontend": no chart library is on the frozen
 * dependency list, so bars/lines render as plain SVG with the app's CSS
 * variables). Multi-series grouped bars + polylines; values are exact
 * numbers from the server payload.
 */

const SERIES_COLORS = [
  "var(--accent)",
  "var(--success, #16a34a)",
  "var(--warning, #d97706)",
  "var(--danger)",
];

const WIDTH = 640;
const HEIGHT = 220;
const PAD = { top: 12, right: 12, bottom: 34, left: 44 };

function niceMax(value: number): number {
  if (value <= 0) return 1;
  const pow = 10 ** Math.floor(Math.log10(value));
  const unit = value / pow;
  const nice = unit <= 1 ? 1 : unit <= 2 ? 2 : unit <= 2.5 ? 2.5 : unit <= 5 ? 5 : 10;
  return nice * pow;
}

function ChartFrame({
  chart,
  children,
  maxValue,
}: {
  chart: ReportChart;
  children: React.ReactNode;
  maxValue: number;
}) {
  const ticks = [0, 0.25, 0.5, 0.75, 1].map((f) => Math.round(maxValue * f * 100) / 100);
  return (
    <figure aria-label={chart.title} className="w-full">
      <svg
        viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
        className="w-full"
        role="img"
        aria-label={chart.title}
      >
        {ticks.map((tick) => {
          const y =
            PAD.top + (1 - tick / maxValue) * (HEIGHT - PAD.top - PAD.bottom);
          return (
            <g key={tick}>
              <line
                x1={PAD.left}
                x2={WIDTH - PAD.right}
                y1={y}
                y2={y}
                stroke="var(--border-subtle)"
                strokeDasharray={tick === 0 ? "0" : "3 4"}
              />
              <text
                x={PAD.left - 6}
                y={y + 3}
                textAnchor="end"
                fontSize="9"
                fill="var(--text-tertiary)"
              >
                {tick >= 1000 ? `${Math.round(tick / 1000)}k` : tick}
              </text>
            </g>
          );
        })}
        {children}
      </svg>
      {chart.series.length > 1 ? (
        <figcaption className="mt-1 flex flex-wrap gap-3">
          {chart.series.map((series, i) => (
            <span
              key={series.name}
              className="inline-flex items-center gap-1.5 text-xs text-[var(--text-secondary)]"
            >
              <span
                className="inline-block h-2.5 w-2.5 rounded-sm"
                style={{ background: SERIES_COLORS[i % SERIES_COLORS.length] }}
              />
              {series.name}
            </span>
          ))}
        </figcaption>
      ) : null}
    </figure>
  );
}

export function SvgChart({ chart }: { chart: ReportChart }) {
  const values = chart.series.flatMap((s) => s.data);
  const maxValue = niceMax(Math.max(1, ...values));
  const plotW = WIDTH - PAD.left - PAD.right;
  const plotH = HEIGHT - PAD.top - PAD.bottom;
  const count = Math.max(1, chart.labels.length);

  if (chart.labels.length === 0) {
    return (
      <p className="text-sm text-[var(--text-tertiary)]">No data for this chart yet.</p>
    );
  }

  if (chart.kind === "line") {
    return (
      <ChartFrame chart={chart} maxValue={maxValue}>
        {chart.series.map((series, si) => {
          const points = chart.labels.map((_, i) => {
            const x = PAD.left + (count === 1 ? plotW / 2 : (i / (count - 1)) * plotW);
            const y = PAD.top + (1 - (series.data[i] ?? 0) / maxValue) * plotH;
            return { x, y };
          });
          const path = points
            .map((p, i) => `${i === 0 ? "M" : "L"}${p.x.toFixed(1)},${p.y.toFixed(1)}`)
            .join(" ");
          return (
            <g key={series.name}>
              <path
                d={path}
                fill="none"
                stroke={SERIES_COLORS[si % SERIES_COLORS.length]}
                strokeWidth="2"
              />
              {points.map((p, i) => (
                <circle key={i} cx={p.x} cy={p.y} r="2.6"
                  fill={SERIES_COLORS[si % SERIES_COLORS.length]} />
              ))}
            </g>
          );
        })}
        {chart.labels.map((label, i) => {
          const x = PAD.left + (count === 1 ? plotW / 2 : (i / (count - 1)) * plotW);
          return (
            <text key={i} x={x} y={HEIGHT - PAD.bottom + 14} textAnchor="middle"
              fontSize="9" fill="var(--text-tertiary)">
              {label}
            </text>
          );
        })}
      </ChartFrame>
    );
  }

  // Grouped bars (one group per label, bars per series).
  const groupW = plotW / count;
  const barW = Math.min(28, (groupW * 0.7) / Math.max(1, chart.series.length));
  return (
    <ChartFrame chart={chart} maxValue={maxValue}>
      {chart.labels.map((_, i) =>
        chart.series.map((series, si) => {
          const value = series.data[i] ?? 0;
          const h = (value / maxValue) * plotH;
          const x =
            PAD.left + i * groupW + groupW / 2 - (barW * chart.series.length) / 2 + si * barW;
          return (
            <rect
              key={`${i}-${si}`}
              x={x}
              y={PAD.top + plotH - h}
              width={Math.max(1.5, barW - 2)}
              height={Math.max(0.5, h)}
              rx="2"
              fill={SERIES_COLORS[si % SERIES_COLORS.length]}
              opacity={si === 0 ? 1 : 0.85}
            >
              <title>{`${series.name}: ${value}`}</title>
            </rect>
          );
        }),
      )}
      {chart.labels.map((label, i) => {
        const x = PAD.left + i * groupW + groupW / 2;
        const truncated = label.length > 14 ? `${label.slice(0, 12)}…` : label;
        return (
          <text key={i} x={x} y={HEIGHT - PAD.bottom + 14} textAnchor="middle"
            fontSize="9" fill="var(--text-tertiary)">
            {truncated}
          </text>
        );
      })}
    </ChartFrame>
  );
}

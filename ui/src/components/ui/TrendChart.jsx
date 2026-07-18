// TrendChart — the one line chart.
//
// Four charts had grown separately with the same anatomy and four sets of
// numbers: UCI trajectory, coherence timeline, risk sparkline, policy history.
// Each drew its own grid, its own threshold dashes, its own "latest point" dot
// and its own ring around the sharpest bend — at slightly different stroke
// weights, tick sizes and label offsets, so the Cognition surface never looked
// like one instrument.
//
// This is that anatomy, once. A view supplies data and MEANING (tones, a
// threshold, which point to ring); the chart owns every pixel decision.
//
//   <TrendChart
//     series={[{ label: "C(t)", values, tone: "success", emphasis: true }]}
//     domain={[0, 1]} grid={[0.6, 0.8, 1.0]}
//     threshold={{ value: 0.82, label: "healthy" }}
//     marker={{ index: 7, tone: "error", title: "sharpest bend" }}
//     xLabels={["w0", "w25", "w50"]} legend
//   />
import { T, TYPE, FONT_MONO } from "@/styles/theme";
import { toneColor } from "./tone";
import { EmptyState } from "./Feedback";

// Geometry. A viewBox with `width: 100%` so the chart is responsive without
// measuring anything — the aspect is fixed, the pixels scale.
const VB_W = 560;
const PAD  = { x: 34, y: 14, bottom: 20 };

const STROKE = { emphasis: 2.2, normal: 1.2 };

/** @param series   [{ label, values:number[], tone, emphasis?, dots?:[{index,tone}] }]
 *                  `emphasis` is the primary line; others render as faint context.
 *  @param domain   [min, max] — fixed, never data-derived, so slope stays honest
 *                  across refreshes.
 *  @param grid     values to draw a horizontal reference line at.
 *  @param threshold{ value, label } — the dashed "healthy" line.
 *  @param mean     draw a dashed mean line at this value (risk-style charts).
 *  @param marker   { index, tone, title } — rings one point (a Δ² bend).
 *  @param xLabels  up to 3 labels spread across the x-axis.
 *  @param format   value → string, for the latest-point label. */
export function TrendChart({
  series = [], domain = [0, 1], grid = [], threshold, mean, marker,
  xLabels = [], height = 130, legend = false, format = (v) => v.toFixed(2),
  empty = "Not enough samples yet.",
}) {
  const live = series.filter(s => Array.isArray(s.values) && s.values.length > 1);
  if (!live.length) return <EmptyState msg={empty} />;

  const [lo, hi] = domain;
  const n  = Math.max(...live.map(s => s.values.length));
  const iW = VB_W - PAD.x * 2;
  const iH = height - PAD.y - PAD.bottom;

  const xs = i => PAD.x + (n <= 1 ? 0 : (i / (n - 1)) * iW);
  const ys = v => {
    const t = (Math.max(lo, Math.min(hi, v)) - lo) / (hi - lo || 1);
    return PAD.y + (1 - t) * iH;
  };

  const points = vals => vals
    .map((v, i) => (v == null ? null : `${xs(i).toFixed(1)},${ys(v).toFixed(1)}`))
    .filter(Boolean)
    .join(" ");

  // The emphasis line owns the latest-value readout; context lines stay quiet.
  const primary = live.find(s => s.emphasis) || live[0];
  const lastVal = primary.values[primary.values.length - 1];
  const lastCol = toneColor(primary.tone);

  return (
    <div>
      <svg
        width="100%" viewBox={`0 0 ${VB_W} ${height}`} role="img"
        aria-label={`${primary.label ?? "trend"} — latest ${format(lastVal)}`}
        style={{ display: "block", overflow: "visible" }}
      >
        {/* Reference grid — labelled on the left so the scale is readable
            without a legend. */}
        {grid.map(g => (
          <g key={g}>
            <line x1={PAD.x} y1={ys(g)} x2={VB_W - PAD.x} y2={ys(g)}
                  stroke={T.border} strokeWidth={1} strokeDasharray="2 4" />
            <text x={PAD.x - 5} y={ys(g) + 3} fill={T.muted} fontSize={8}
                  textAnchor="end" fontFamily={FONT_MONO}>
              {format(g)}
            </text>
          </g>
        ))}

        {/* Threshold — heavier dash than the grid, labelled at the right edge:
            it is a judgement ("healthy"), not just another gridline. */}
        {threshold != null && (
          <g>
            <line x1={PAD.x} y1={ys(threshold.value)} x2={VB_W - PAD.x} y2={ys(threshold.value)}
                  stroke={T.accent} strokeWidth={1} strokeDasharray="4 3" opacity={0.55} />
            {threshold.label && (
              <text x={VB_W - PAD.x + 3} y={ys(threshold.value) + 3}
                    fill={T.muted} fontSize={7}>{threshold.label}</text>
            )}
          </g>
        )}

        {/* A mean line runs THROUGH the data by definition, so its label has no
            safe home inside the plot: at the right edge it collided with the
            latest-value readout, and inset at the left it landed on the line
            itself. It sits in the outer gutter, named but not numbered, nudged
            clear of the last-point label — the value belongs on a stat card,
            where there is room to say what it is the mean OF. */}
        {mean != null && (
          <g>
            <line x1={PAD.x} y1={ys(mean)} x2={VB_W - PAD.x} y2={ys(mean)}
                  stroke={T.border} strokeWidth={1} strokeDasharray="4 3" />
            <text x={VB_W - PAD.x + 3} y={ys(mean) - 7} fill={T.muted} fontSize={7}>mean</text>
          </g>
        )}

        {/* Context lines first, emphasis last — the primary series must never
            be crossed over by a faint one. */}
        {live.filter(s => s !== primary).map(s => (
          <polyline key={s.label} points={points(s.values)} fill="none"
                    stroke={toneColor(s.tone)} strokeWidth={STROKE.normal} opacity={0.45}
                    strokeLinejoin="round" strokeLinecap="round" />
        ))}
        <polyline points={points(primary.values)} fill="none"
                  stroke={lastCol} strokeWidth={STROKE.emphasis}
                  strokeLinejoin="round" strokeLinecap="round" />

        {/* Categorical dots — a risk chart colors each sample by reflect level. */}
        {live.flatMap(s => (s.dots || []).map(d => (
          <circle key={`${s.label}-${d.index}`} cx={xs(d.index)} cy={ys(s.values[d.index] ?? lo)}
                  r={2.5} fill={toneColor(d.tone)} opacity={0.85} />
        )))}

        {/* The bend ring — a leading indicator, so it is an annotation on the
            line rather than a change to the line itself. */}
        {marker && marker.index >= 0 && primary.values[marker.index] != null && (
          <circle cx={xs(marker.index)} cy={ys(primary.values[marker.index])} r={4.5}
                  fill="none" stroke={toneColor(marker.tone)} strokeWidth={1.6}>
            {marker.title && <title>{marker.title}</title>}
          </circle>
        )}

        {/* Latest point + its value. */}
        <circle cx={xs(primary.values.length - 1)} cy={ys(lastVal)} r={3.2} fill={lastCol} />
        <text x={xs(primary.values.length - 1) + 6} y={ys(lastVal) + 3.5}
              fill={lastCol} fontSize={9} fontWeight={700} fontFamily={FONT_MONO}>
          {format(lastVal)}
        </text>

        {/* Baseline + x labels. */}
        <line x1={PAD.x} y1={PAD.y + iH} x2={VB_W - PAD.x} y2={PAD.y + iH} stroke={T.border} />
        {xLabels.slice(0, 3).map((label, i, arr) => (
          <text key={label + i} x={PAD.x + (arr.length === 1 ? 0 : (i / (arr.length - 1)) * iW)}
                y={height - 4} fill={T.muted} fontSize={8}
                textAnchor={i === 0 ? "start" : i === arr.length - 1 ? "end" : "middle"}
                fontFamily={FONT_MONO}>
            {label}
          </text>
        ))}
      </svg>

      {legend && live.length > 1 && (
        <div style={{ display: "flex", flexWrap: "wrap", gap: 14, marginTop: 8 }}>
          {live.map(s => (
            <span key={s.label} style={{ display: "flex", alignItems: "center", gap: 5 }}>
              <span style={{
                width: 12, height: s.emphasis ? 2.5 : 1.5, borderRadius: 2,
                background: toneColor(s.tone), opacity: s.emphasis ? 1 : 0.5,
              }} />
              <span style={{ ...TYPE.micro, color: T.muted }}>{s.label}</span>
            </span>
          ))}
        </div>
      )}
    </div>
  );
}

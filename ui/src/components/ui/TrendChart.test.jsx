// TrendChart.test.jsx — the guarantees that make one chart safe to share.
//
// Four charts collapsed into this one, so the risk moved: a change made for the
// coherence timeline must not quietly break the risk sparkline. These pin the
// contract each of the four relies on.
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { TrendChart } from "./TrendChart";

const series = (values, extra = {}) => [{ label: "C(t)", values, tone: "success", emphasis: true, ...extra }];

describe("TrendChart", () => {
  it("renders an empty state instead of a chart for a single point", () => {
    // A slope drawn through one sample is a straight line that means nothing.
    render(<TrendChart series={series([0.9])} empty="Needs two windows." />);
    expect(screen.getByText("Needs two windows.")).toBeInTheDocument();
    expect(screen.queryByRole("img")).not.toBeInTheDocument();
  });

  it("labels itself with the primary series and its latest value", () => {
    render(<TrendChart series={series([0.7, 0.8, 0.912])} format={v => v.toFixed(3)} />);
    expect(screen.getByRole("img")).toHaveAccessibleName("C(t) — latest 0.912");
  });

  it("scales to the given domain, not to the data", () => {
    // The honesty rule: a fixed 0–100 UCI axis means a 3-point wobble looks like
    // a 3-point wobble. An auto-fitted axis would render it as a cliff.
    const { container } = render(
      <TrendChart domain={[0, 100]} height={100} series={series([50, 50, 50])} />
    );
    const pts = container.querySelector("polyline").getAttribute("points");
    const ys  = pts.split(" ").map(p => Number(p.split(",")[1]));
    expect(new Set(ys).size).toBe(1);           // flat data draws a flat line
    expect(ys[0]).toBeGreaterThan(20);          // and sits mid-axis, not at the top
  });

  it("clamps values outside the domain instead of drawing off-canvas", () => {
    const { container } = render(
      <TrendChart domain={[0, 1]} height={100} series={series([-5, 0.5, 99])} />
    );
    const ys = container.querySelector("polyline").getAttribute("points")
      .split(" ").map(p => Number(p.split(",")[1]));
    expect(Math.min(...ys)).toBeGreaterThanOrEqual(0);
    expect(Math.max(...ys)).toBeLessThanOrEqual(100);
  });

  it("skips null samples rather than dropping the line to zero", () => {
    const { container } = render(
      <TrendChart domain={[0, 1]} series={series([0.8, null, 0.9])} />
    );
    expect(container.querySelector("polyline").getAttribute("points").split(" ")).toHaveLength(2);
  });

  it("draws the threshold with its label", () => {
    render(<TrendChart series={series([0.7, 0.9])} threshold={{ value: 0.82, label: "healthy" }} />);
    expect(screen.getByText("healthy")).toBeInTheDocument();
  });

  it("rings a marked point and titles it", () => {
    const { container } = render(
      <TrendChart series={series([0.9, 0.6, 0.8])}
                  marker={{ index: 1, tone: "error", title: "Sharpest bend" }} />
    );
    expect(container.querySelector("title")).toHaveTextContent("Sharpest bend");
  });

  it("ignores a marker pointing past the end of the data", () => {
    // Curvature indices are computed from a different-length array; an
    // off-by-one must not crash the whole Diagnostics section.
    const { container } = render(
      <TrendChart series={series([0.9, 0.8])} marker={{ index: 47, tone: "error", title: "x" }} />
    );
    expect(container.querySelector("title")).toBeNull();
  });

  it("draws context series behind one emphasis line, and legends them all", () => {
    const { container } = render(
      <TrendChart legend series={[
        { label: "C(t)",    values: [0.8, 0.9], tone: "success", emphasis: true },
        { label: "routing", values: [0.7, 0.75], tone: "accent" },
        { label: "memory",  values: [0.6, 0.65], tone: "purple" },
      ]} />
    );
    const lines = container.querySelectorAll("polyline");
    expect(lines).toHaveLength(3);
    // The primary line is drawn LAST so a faint context line never crosses over it.
    expect(lines[lines.length - 1].getAttribute("stroke-width")).toBe("2.2");
    ["C(t)", "routing", "memory"].forEach(l => expect(screen.getByText(l)).toBeInTheDocument());
  });

  it("places a dot per categorical sample (the risk-by-level read)", () => {
    const { container } = render(
      <TrendChart domain={[0, 1]} series={series([0.2, 0.6, 0.9], {
        dots: [{ index: 0, tone: "success" }, { index: 1, tone: "warn" }, { index: 2, tone: "error" }],
      })} />
    );
    // three level dots + the latest-point dot
    expect(container.querySelectorAll("circle")).toHaveLength(4);
  });
});

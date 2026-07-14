/** The gold range slider. The track fills gold up to the current value; the
 *  thumb is a white-ringed gold disc. Chrome lives in styles/index.css
 *  (.gold-range) because it needs ::-webkit-slider-thumb. */
export function Slider({ value, onChange, min, max, step = 1, width = 170, label }) {
  const pct = ((value - min) / (max - min)) * 100;
  return (
    <input
      type="range"
      className="gold-range"
      aria-label={label}
      min={min} max={max} step={step}
      value={value}
      onChange={e => onChange(step % 1 === 0 ? parseInt(e.target.value, 10) : parseFloat(e.target.value))}
      style={{ width, "--pct": `${pct}%` }}
    />
  );
}

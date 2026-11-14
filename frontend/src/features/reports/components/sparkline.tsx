// DDR-117 (9): no chart library. A small inline SVG line with a text alternative; decorative shapes are hidden
// from assistive technology and the values are given in words.
export function Sparkline({ values, label }: { values: number[]; label: string }) {
  if (values.length < 2) return null;
  const w = 120;
  const h = 32;
  const max = Math.max(...values, 1);
  const step = w / (values.length - 1);
  const points = values.map((v, i) => `${(i * step).toFixed(1)},${(h - (v / max) * (h - 4) - 2).toFixed(1)}`);
  const total = values.reduce((a, b) => a + b, 0);
  return (
    <figure className="mt-2" aria-label={`${label}: daily values ${values.join(", ")} (total ${total})`}>
      <svg width={w} height={h} viewBox={`0 0 ${w} ${h}`} aria-hidden="true" focusable="false">
        <polyline points={points.join(" ")} fill="none" stroke="currentColor" strokeWidth="2" />
      </svg>
    </figure>
  );
}

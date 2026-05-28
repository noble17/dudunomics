// frontend/components/screener/radar-chart.tsx
interface RadarPoint { label: string; value: number }

interface Props { points: RadarPoint[] }

export function RadarChart({ points }: Props) {
  const n = points.length;
  const cx = 100, cy = 100, r = 75;
  const angleStep = (2 * Math.PI) / n;

  const toXY = (i: number, radius: number) => ({
    x: cx + radius * Math.sin(i * angleStep - Math.PI / 2),
    y: cy - radius * Math.cos(i * angleStep - Math.PI / 2),
  });

  const bgPolygons = [0.25, 0.5, 0.75, 1.0].map((scale) =>
    points.map((_, i) => toXY(i, r * scale)).map((p) => `${p.x},${p.y}`).join(" ")
  );

  const dataPolygon = points
    .map((p, i) => toXY(i, r * Math.max(0, Math.min(1, p.value ?? 0))))
    .map((p) => `${p.x},${p.y}`)
    .join(" ");

  return (
    <svg viewBox="0 0 200 200" className="w-full h-full">
      {/* 배경 격자 */}
      {bgPolygons.map((pts, i) => (
        <polygon key={i} points={pts} fill="none" stroke="#e2e8f0" strokeWidth="0.8" />
      ))}
      {/* 축선 */}
      {points.map((_, i) => {
        const p = toXY(i, r);
        return <line key={i} x1={cx} y1={cy} x2={p.x} y2={p.y} stroke="#e2e8f0" strokeWidth="0.8" />;
      })}
      {/* 데이터 영역 */}
      <polygon points={dataPolygon} fill="rgba(59,130,246,0.18)" stroke="#3b82f6" strokeWidth="1.5" />
      {/* 레이블 */}
      {points.map((p, i) => {
        const { x, y } = toXY(i, r + 16);
        return (
          <text
            key={i}
            x={x}
            y={y}
            textAnchor="middle"
            dominantBaseline="middle"
            fontSize="9"
            fill="#475569"
            fontFamily="sans-serif"
          >
            {p.label}
          </text>
        );
      })}
    </svg>
  );
}

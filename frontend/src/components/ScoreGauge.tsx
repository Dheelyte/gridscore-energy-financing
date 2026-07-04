import { useEffect, useState } from "react";

const MIN = 300;
const MAX = 850;

const TIER_COLOR: Record<string, string> = {
  A: "#27d08a",
  B: "#6ee7b7",
  C: "#fbbf24",
  D: "#fb923c",
  E: "#f87171",
};

/** Semicircular 300–850 Energy Credit Score gauge. The arc sweeps in on mount
 *  (CSS transition); the number is shown immediately. */
export function ScoreGauge({
  score,
  tier,
  size = 220,
}: {
  score: number;
  tier: string;
  size?: number;
}) {
  const [mounted, setMounted] = useState(false);
  useEffect(() => {
    const id = requestAnimationFrame(() => setMounted(true));
    return () => cancelAnimationFrame(id);
  }, []);

  const r = size / 2 - 16;
  const cx = size / 2;
  const cy = size / 2;
  const circumference = Math.PI * r; // half circle
  const pct = Math.min(Math.max((score - MIN) / (MAX - MIN), 0), 1);
  const color = TIER_COLOR[tier] ?? "#27d08a";

  return (
    <div className="relative" style={{ width: size, height: size / 2 + 28 }}>
      <svg width={size} height={size / 2 + 28} viewBox={`0 0 ${size} ${size / 2 + 28}`}>
        <path
          d={`M ${cx - r} ${cy} A ${r} ${r} 0 0 1 ${cx + r} ${cy}`}
          fill="none"
          stroke="hsl(var(--muted))"
          strokeWidth={12}
          strokeLinecap="round"
        />
        <path
          d={`M ${cx - r} ${cy} A ${r} ${r} 0 0 1 ${cx + r} ${cy}`}
          fill="none"
          stroke={color}
          strokeWidth={12}
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={circumference * (1 - (mounted ? pct : 0))}
          style={{ transition: "stroke-dashoffset 900ms cubic-bezier(0.22,1,0.36,1)" }}
        />
      </svg>
      <div className="absolute inset-x-0 top-[42%] flex flex-col items-center">
        <span className="font-mono text-4xl font-bold tabular-nums" style={{ color }}>
          {Math.round(score)}
        </span>
        <span className="text-xs text-muted-foreground">Energy Credit Score · Tier {tier}</span>
      </div>
    </div>
  );
}

"use client"

import { cn } from "@/lib/utils"

type RiskGaugeProps = {
  /** Model-predicted score (1–5). When null, show "—" (no default). */
  value: number | null
  max?: number
  label: string
  className?: string
}

function clamp(n: number, min: number, max: number) {
  return Math.min(max, Math.max(min, n))
}

export function RiskGauge({ value, max = 5, label, className }: RiskGaugeProps) {
  const size = 240
  const stroke = 24
  const r = (size - stroke) / 2
  const c = 2 * Math.PI * r

  const startAngle = 180
  const sweepAngle = 180
  const hasScore = value !== null && value !== undefined && !Number.isNaN(value)
  const progress = hasScore ? clamp(value / max, 0, 1) : 0
  const dash = (sweepAngle / 360) * c
  const dashOffset = dash * (1 - progress)

  return (
    <div className={cn("relative mx-auto w-full max-w-[280px] rounded-3xl bg-card p-6 shadow-md", className)}>
      <svg
        width={size}
        height={size}
        viewBox={`0 0 ${size} ${size}`}
        className="mx-auto block"
        aria-label={`Risk gauge: ${label}`}
        role="img"
      >
        <g transform={`rotate(${startAngle} ${size / 2} ${size / 2})`}>
          <circle
            cx={size / 2}
            cy={size / 2}
            r={r}
            fill="none"
            stroke="var(--muted)"
            strokeWidth={stroke}
            strokeLinecap="round"
            strokeDasharray={`${dash} ${c}`}
            opacity={0.5}
          />
          <circle
            cx={size / 2}
            cy={size / 2}
            r={r}
            fill="none"
            stroke="var(--primary)"
            strokeWidth={stroke}
            strokeLinecap="round"
            strokeDasharray={`${dash} ${c}`}
            strokeDashoffset={dashOffset}
          />
        </g>
      </svg>

      <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center">
        <div className="text-5xl font-bold leading-none tabular-nums">
          {hasScore
            ? Number.isInteger(value) ? value : (value as number).toFixed(1)
            : "—"}
        </div>
        <div className="mt-1 text-xs font-medium uppercase tracking-wide text-muted-foreground">
          Risk score
        </div>
        <div className="mt-2 text-base font-medium text-muted-foreground">
          {hasScore ? label : "No prediction"}
        </div>
      </div>
    </div>
  )
}


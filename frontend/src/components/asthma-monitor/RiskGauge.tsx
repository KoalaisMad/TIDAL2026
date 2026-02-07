"use client"

import * as React from "react"

import { cn } from "@/lib/utils"

type RiskGaugeProps = {
  value: number
  max?: number
  label: string
  className?: string
}

function clamp(n: number, min: number, max: number) {
  return Math.min(max, Math.max(min, n))
}

export function RiskGauge({ value, max = 10, label, className }: RiskGaugeProps) {
  const size = 220
  const stroke = 18
  const r = (size - stroke) / 2
  const c = 2 * Math.PI * r

  // top half-ish arc, matching the screenshot
  const startAngle = 225
  const sweepAngle = 270
  const progress = clamp(value / max, 0, 1)
  const dash = (sweepAngle / 360) * c
  const dashOffset = dash * (1 - progress)

  return (
    <div className={cn("relative mx-auto w-full max-w-[260px]", className)}>
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
            stroke="var(--border)"
            strokeWidth={stroke}
            strokeLinecap="round"
            strokeDasharray={`${dash} ${c}`}
            opacity={0.4}
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
        <div className="text-4xl font-semibold leading-none">{value}</div>
        <div className="mt-1 text-sm font-semibold text-muted-foreground">
          {label}
        </div>
        <div className="text-sm font-semibold text-muted-foreground">Risk</div>
      </div>
    </div>
  )
}


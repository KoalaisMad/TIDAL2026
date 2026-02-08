"use client"

import * as React from "react"
import { Loader2 } from "lucide-react"
import { cn } from "@/lib/utils"

type PredictionsLoadingIndicatorProps = {
  message: string
  submessage?: string
  /** Show a skeleton-style gauge placeholder */
  showGaugeSkeleton?: boolean
  className?: string
}

export function PredictionsLoadingIndicator({
  message,
  submessage,
  showGaugeSkeleton = true,
  className,
}: PredictionsLoadingIndicatorProps) {
  return (
    <div
      className={cn(
        "flex flex-col items-center justify-center gap-4 rounded-3xl border border-border/60 bg-card/80 py-8 shadow-sm",
        className
      )}
      role="status"
      aria-live="polite"
      aria-label={message}
    >
      {showGaugeSkeleton && (
        <div className="relative mx-auto flex h-[240px] w-[240px] max-w-[280px] items-center justify-center rounded-3xl bg-muted/30">
          <div className="absolute inset-0 flex items-center justify-center rounded-3xl bg-gradient-to-b from-primary/5 to-transparent" />
          <div className="relative z-10 flex flex-col items-center gap-4">
            <Loader2
              className="size-12 text-primary animate-spin"
              strokeWidth={2}
              aria-hidden
            />
            <span className="text-3xl font-bold tabular-nums text-muted-foreground/70">
              —
            </span>
            <span className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
              Risk score
            </span>
          </div>
        </div>
      )}
      {!showGaugeSkeleton && (
        <Loader2
          className="size-10 text-primary animate-spin"
          strokeWidth={2}
          aria-hidden
        />
      )}
      <div className="flex flex-col items-center gap-1 text-center">
        <p className="text-sm font-medium text-foreground">{message}</p>
        {submessage && (
          <p className="text-xs text-muted-foreground">{submessage}</p>
        )}
      </div>
      {/* Animated dots for "in progress" feel */}
      <div className="flex gap-1.5" aria-hidden>
        {[0, 1, 2].map((i) => (
          <span
            key={i}
            className="size-2 rounded-full bg-primary/60 animate-bounce"
            style={{
              animationDelay: `${i * 0.15}s`,
              animationDuration: "0.6s",
            }}
          />
        ))}
      </div>
    </div>
  )
}

"use client"

import * as React from "react"

import { cn } from "@/lib/utils"
import type { DayItem } from "./mockData"

type DateStripProps = {
  days: DayItem[]
  selectedId: string
  onSelect: (id: string) => void
}

export function DateStrip({ days, selectedId, onSelect }: DateStripProps) {
  return (
    <div className="rounded-2xl bg-background shadow-sm">
      <div className="scrollbar-none flex snap-x snap-proximity gap-2 overflow-x-auto p-2 [scrollbar-gutter:stable] md:justify-between md:overflow-visible md:p-3">
        {days.map((d) => {
          const selected = d.id === selectedId
          return (
            <button
              key={d.id}
              type="button"
              onClick={() => onSelect(d.id)}
              aria-pressed={selected}
              className={cn(
                "snap-start rounded-2xl border px-2.5 py-2 text-center transition-colors sm:px-3",
                "min-w-[46px] flex-none sm:min-w-[52px] md:min-w-0 md:flex-1",
                selected
                  ? "border-transparent bg-primary text-primary-foreground shadow"
                  : "border-border/60 bg-card text-foreground hover:bg-muted"
              )}
            >
              <div className={cn("text-[10px] sm:text-[11px]", selected && "opacity-90")}>
                {d.dow}
              </div>
              <div className="text-[13px] font-semibold leading-5 sm:text-sm">
                {d.dayOfMonth}
              </div>
            </button>
          )
        })}
      </div>
    </div>
  )
}


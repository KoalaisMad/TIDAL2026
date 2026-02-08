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
    <div className="rounded-3xl bg-card shadow-md">
      <div className="scrollbar-none flex snap-x snap-proximity gap-3 overflow-x-auto p-4 [scrollbar-gutter:stable] md:justify-between md:overflow-visible md:p-5">
        {days.map((d) => {
          const selected = d.id === selectedId
          return (
            <button
              key={d.id}
              type="button"
              onClick={() => onSelect(d.id)}
              aria-pressed={selected}
              className={cn(
                "snap-start rounded-3xl border-0 px-4 py-3 text-center transition-all sm:px-5",
                "min-w-[52px] flex-none sm:min-w-[60px] md:min-w-0 md:flex-1",
                selected
                  ? "bg-primary text-primary-foreground shadow-lg scale-105"
                  : "bg-muted/50 text-foreground hover:bg-muted"
              )}
            >
              <div className={cn("text-[11px] font-medium sm:text-xs", selected && "opacity-90")}>
                {d.dow}
              </div>
              <div className="text-sm font-bold leading-6 sm:text-base">
                {d.dayOfMonth}
              </div>
            </button>
          )
        })}
      </div>
    </div>
  )
}


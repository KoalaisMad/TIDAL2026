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
      <div className="flex gap-2 overflow-x-auto p-3 md:justify-between md:overflow-visible">
        {days.map((d) => {
          const selected = d.id === selectedId
          return (
            <button
              key={d.id}
              type="button"
              onClick={() => onSelect(d.id)}
              aria-pressed={selected}
              className={cn(
                "min-w-[52px] rounded-2xl border px-3 py-2 text-center transition-colors",
                selected
                  ? "border-transparent bg-primary text-primary-foreground shadow"
                  : "border-border/60 bg-card text-foreground hover:bg-muted"
              )}
            >
              <div className={cn("text-[11px]", selected && "opacity-90")}>
                {d.dow}
              </div>
              <div className="text-sm font-semibold leading-5">
                {d.dayOfMonth}
              </div>
            </button>
          )
        })}
      </div>
    </div>
  )
}


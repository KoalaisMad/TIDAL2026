"use client"

import * as React from "react"

import { cn } from "@/lib/utils"
import type { RiskFactor } from "./mockData"

type RiskFactorsProps = {
  items: RiskFactor[]
  className?: string
}

export function RiskFactors({ items, className }: RiskFactorsProps) {
  return (
    <section className={cn("space-y-3", className)}>
      <h2 className="text-sm font-semibold text-foreground">Active Risk Factors</h2>
      <div className="grid grid-cols-2 gap-3">
        {items.map((it) => {
          const Icon = it.icon
          return (
            <div
              key={it.id}
              className="flex items-center justify-between rounded-2xl bg-primary/10 px-3 py-3"
            >
              <div className="flex items-center gap-2">
                <div className="flex h-8 w-8 items-center justify-center rounded-xl bg-primary/15 text-primary">
                  <Icon className="h-4 w-4" aria-hidden="true" />
                </div>
                <div className="text-xs font-medium text-foreground">
                  {it.label}
                </div>
              </div>
              <span
                className="h-2 w-2 rounded-full bg-primary"
                aria-label="Active"
              />
            </div>
          )
        })}
      </div>
    </section>
  )
}


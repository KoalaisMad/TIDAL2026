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
    <section className={cn("space-y-4", className)}>
      <h2 className="text-sm font-bold text-foreground">Active Risk Factors</h2>
      <div className="grid grid-cols-2 gap-4">
        {items.map((it) => {
          const Icon = it.icon
          return (
            <div
              key={it.id}
              className="flex items-center justify-between rounded-3xl bg-card px-4 py-4 shadow-md"
            >
              <div className="flex items-center gap-3">
                <div className="flex h-10 w-10 items-center justify-center rounded-2xl bg-primary/20 text-primary">
                  <Icon className="h-5 w-5" aria-hidden="true" />
                </div>
                <div className="text-xs font-medium text-foreground">
                  {it.label}
                </div>
              </div>
              <span
                className="h-2.5 w-2.5 rounded-full bg-primary shadow-sm"
                aria-label="Active"
              />
            </div>
          )
        })}
      </div>
    </section>
  )
}


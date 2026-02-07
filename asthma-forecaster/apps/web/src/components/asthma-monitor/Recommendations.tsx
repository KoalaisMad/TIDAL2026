import * as React from "react"

import {
  Card,
  CardContent,
  CardDescription,
  CardTitle,
} from "@/components/ui/card"
import { cn } from "@/lib/utils"
import type { Recommendation } from "./mockData"

type RecommendationsProps = {
  items: Recommendation[]
  className?: string
}

export function Recommendations({ items, className }: RecommendationsProps) {
  return (
    <section className={cn("space-y-3", className)}>
      <h2 className="text-sm font-semibold text-foreground">Recommendations</h2>
      <div className="space-y-3">
        {items.map((r, idx) => (
          <Card key={r.id} className="border-border/60">
            <CardContent className="flex items-start gap-3 p-4">
              <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-primary/10 text-xs font-semibold text-primary">
                {idx + 1}
              </div>
              <div className="space-y-1">
                <CardTitle className="text-sm">{r.title}</CardTitle>
                <CardDescription className="text-xs leading-5">
                  {r.description}
                </CardDescription>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>
    </section>
  )
}


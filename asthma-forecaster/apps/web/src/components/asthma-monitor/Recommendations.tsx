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
    <section className={cn("space-y-4", className)}>
      <h2 className="text-sm font-bold text-foreground">Recommendations</h2>
      <div className="space-y-4">
        {items.map((r, idx) => (
          <Card key={r.id}>
            <CardContent className="flex items-start gap-4 p-5">
              <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-primary/15 text-xs font-bold text-primary">
                {idx + 1}
              </div>
              <div className="space-y-2">
                <CardTitle className="text-sm font-bold">{r.title}</CardTitle>
                <CardDescription className="text-xs leading-relaxed">
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


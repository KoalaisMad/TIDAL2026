"use client"

import * as React from "react"
import { ArrowRight } from "lucide-react"

import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { cn } from "@/lib/utils"

type RiskTabsProps = {
  value: "environmental" | "personalized"
  onValueChange: (v: RiskTabsProps["value"]) => void
  className?: string
}

export function RiskTabs({ value, onValueChange, className }: RiskTabsProps) {
  return (
    <Tabs
      value={value}
      onValueChange={(v) => onValueChange(v as RiskTabsProps["value"])}
      className={cn("w-full", className)}
    >
      <TabsList className="w-full justify-between bg-transparent p-0 gap-6">
        <TabsTrigger
          value="environmental"
          className="rounded-none bg-transparent px-0 text-base font-medium text-muted-foreground data-[state=active]:bg-transparent data-[state=active]:shadow-none data-[state=active]:text-foreground data-[state=active]:font-bold"
        >
          Environmental Risk
        </TabsTrigger>

        <TabsTrigger
          value="personalized"
          className="rounded-none bg-transparent px-0 text-base font-medium text-muted-foreground data-[state=active]:bg-transparent data-[state=active]:shadow-none data-[state=active]:text-foreground data-[state=active]:font-bold"
        >
          <span className="inline-flex items-center gap-2">
            Personalized Risk <ArrowRight className="h-5 w-5" aria-hidden="true" />
          </span>
        </TabsTrigger>
      </TabsList>
    </Tabs>
  )
}


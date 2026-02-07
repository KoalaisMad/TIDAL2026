"use client"

import * as React from "react"

import { Button } from "@/components/ui/button"
import { cn } from "@/lib/utils"
import { layout, spacing } from "@/theme"

import { DateStrip } from "./DateStrip"
import { Header } from "./Header"
import { Recommendations } from "./Recommendations"
import { RiskFactors } from "./RiskFactors"
import { RiskGauge } from "./RiskGauge"
import { RiskTabs } from "./RiskTabs"
import { recommendations, riskFactors, weekDays } from "./mockData"

export function AsthmaMonitorScreen() {
  const [tab, setTab] = React.useState<"environmental" | "personalized">(
    "environmental"
  )
  const [selectedDayId, setSelectedDayId] = React.useState<string>("sat")

  // TODO(api): Replace with backend-calculated score + label per selected day + selected tab.
  const riskScore = 3
  const riskLabel = "Moderate"

  return (
    <div className={layout.pageBg}>
      <main className={layout.container}>
        <div className={cn("flex flex-col", spacing.sectionGap)}>
          <Header title="Asthma Monitor" />

          <RiskTabs value={tab} onValueChange={setTab} />

          <DateStrip
            days={[...weekDays]}
            selectedId={selectedDayId}
            onSelect={(id) => setSelectedDayId(id)}
          />

          {/* Mobile-first: single column; Desktop: use space with a 2-col grid */}
          <div className="grid gap-6 md:grid-cols-2 md:items-start">
            <div className="space-y-6">
              <RiskGauge value={riskScore} label={riskLabel} />
              <RiskFactors items={[...riskFactors]} />
            </div>

            <div className="space-y-6">
              <Recommendations items={[...recommendations]} />
            </div>
          </div>

          <div className="sticky bottom-4 flex justify-center pt-2 md:static">
            <Button
              size="pill"
              className="w-full shadow-sm md:w-fit md:px-10"
              onClick={() => {
                // TODO(api): Hook up navigation / fetch personalized risk.
                setTab("personalized")
              }}
            >
              Get Personalized Risk
            </Button>
          </div>
        </div>
      </main>
    </div>
  )
}


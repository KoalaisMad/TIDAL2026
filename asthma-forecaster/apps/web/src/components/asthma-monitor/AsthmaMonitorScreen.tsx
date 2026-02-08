"use client"

import * as React from "react"
import { Droplets, Sprout, Thermometer, Wind } from "lucide-react"

import { Button } from "@/components/ui/button"
import { cn } from "@/lib/utils"
import { layout, spacing } from "@/theme"

import { DateStrip } from "./DateStrip"
import { Header } from "./Header"
import { Recommendations } from "./Recommendations"
import { RiskFactors } from "./RiskFactors"
import { RiskGauge } from "./RiskGauge"
import { RiskTabs } from "./RiskTabs"
import { weekDays, type Recommendation, type RiskFactor } from "./mockData"

type ApiRiskLevel = "low" | "moderate" | "high"
type ApiRiskFactor = {
  id: string
  label: string
  iconKey: "sprout" | "wind" | "thermometer" | "droplets"
}
type ApiRiskResponse = {
  date: string
  risk: { score: number; level: ApiRiskLevel; label: string }
  activeRiskFactors: ApiRiskFactor[]
}
type ApiRecommendationsResponse = {
  date: string
  riskLevel: ApiRiskLevel
  recommendations: Recommendation[]
}

const ICONS: Record<ApiRiskFactor["iconKey"], RiskFactor["icon"]> = {
  sprout: Sprout,
  wind: Wind,
  thermometer: Thermometer,
  droplets: Droplets,
}

function toIsoDateForSelectedDay(selectedDayId: string) {
  const today = new Date()
  const year = today.getFullYear()
  const month = today.getMonth()
  const dayOfMonth =
    weekDays.find((d) => d.id === selectedDayId)?.dayOfMonth ?? today.getDate()
  const d = new Date(year, month, dayOfMonth)
  return d.toISOString().slice(0, 10)
}

export function AsthmaMonitorScreen() {
  const [tab, setTab] = React.useState<"environmental" | "personalized">(
    "environmental"
  )
  const [selectedDayId, setSelectedDayId] = React.useState<string>("sat")

  const [riskScore, setRiskScore] = React.useState<number>(3)
  const [riskLabel, setRiskLabel] = React.useState<string>("Moderate")
  const [activeRiskFactors, setActiveRiskFactors] = React.useState<RiskFactor[]>(
    []
  )
  const [recs, setRecs] = React.useState<Recommendation[]>([])

  React.useEffect(() => {
    const controller = new AbortController()
    const date = toIsoDateForSelectedDay(selectedDayId)

    async function load() {
      try {
        const riskRes = await fetch(`/api/risk?date=${encodeURIComponent(date)}`, {
          signal: controller.signal,
        })
        if (!riskRes.ok) return
        const riskData = (await riskRes.json()) as ApiRiskResponse

        setRiskScore(riskData.risk.score)
        setRiskLabel(riskData.risk.label)
        setActiveRiskFactors(
          riskData.activeRiskFactors.map((f) => ({
            id: f.id,
            label: f.label,
            icon: ICONS[f.iconKey],
          }))
        )

        const recsRes = await fetch(
          `/api/recommendations?date=${encodeURIComponent(date)}&riskLevel=${encodeURIComponent(
            riskData.risk.level
          )}`,
          { signal: controller.signal }
        )
        if (!recsRes.ok) return
        const recsData = (await recsRes.json()) as ApiRecommendationsResponse
        setRecs(recsData.recommendations)
      } catch {
        // keep existing UI defaults if the stub fetch fails
      }
    }

    void load()
    return () => controller.abort()
  }, [selectedDayId])

  return (
    <div className={layout.pageBg}>
      <main className={layout.container}>
        <div className={cn("flex flex-col", spacing.sectionGap)}>
          <Header title="Breathe Well" />

          <RiskTabs value={tab} onValueChange={setTab} />

          <DateStrip
            days={[...weekDays]}
            selectedId={selectedDayId}
            onSelect={(id) => setSelectedDayId(id)}
          />

          {/* Mobile-first: single column; Desktop: use space with a 2-col grid */}
          <div className="grid gap-8 md:grid-cols-2 md:items-start">
            <div className="space-y-8">
              <RiskGauge value={riskScore} label={riskLabel} />
              <RiskFactors items={activeRiskFactors} />
            </div>

            <div className="space-y-8">
              <Recommendations items={recs} />
            </div>
          </div>

          <div className="sticky bottom-6 flex justify-center pt-4 md:static">
            <Button
              size="pill"
              className="w-full md:w-fit md:px-12"
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


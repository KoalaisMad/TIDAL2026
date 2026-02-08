"use client"

import * as React from "react"
import { Droplets, Sprout, Thermometer, Wind } from "lucide-react"
import { useSession, signIn } from "next-auth/react"
import { useRouter } from "next/navigation"

import { Button } from "@/components/ui/button"
import { cn } from "@/lib/utils"
import { layout, spacing } from "@/theme"

import { DateStrip } from "./DateStrip"
import { Header } from "./Header"
import { Recommendations } from "./Recommendations"
import { RiskFactors } from "./RiskFactors"
import { RiskGauge } from "./RiskGauge"
import { RiskTabs } from "./RiskTabs"
import { useGeolocation } from "./useGeolocation"
import { getWeekDaysFromToday, type DayItem, type Recommendation, type RiskFactor } from "./mockData"

type ApiRiskLevel = "low" | "moderate" | "high"
type ApiRiskFactor = {
  id: string
  label: string
  iconKey: "sprout" | "wind" | "thermometer" | "droplets"
}
type WeekDayData = {
  date: string
  risk: { score: number; level: string; label: string }
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

function dateForSelectedDay(selectedDayId: string, weekDays: DayItem[]): string {
  if (/^\d{4}-\d{2}-\d{2}$/.test(selectedDayId)) return selectedDayId
  const day = weekDays.find((d) => d.id === selectedDayId)
  if (day?.date) return day.date
  if (day?.dayOfMonth != null) {
    const today = new Date()
    const d = new Date(today.getFullYear(), today.getMonth(), day.dayOfMonth)
    return d.toISOString().slice(0, 10)
  }
  return new Date().toISOString().slice(0, 10)
}

export function AsthmaMonitorScreen() {
  const router = useRouter()
  const { data: session, status } = useSession()
  const { location, status: locationStatus, requestLocation } = useGeolocation()
  const [tab, setTab] = React.useState<"environmental" | "personalized">(
    "environmental"
  )
  const weekDays = React.useMemo(() => getWeekDaysFromToday(), [])
  const todayIso = weekDays[0]?.id ?? new Date().toISOString().slice(0, 10)
  const [selectedDayId, setSelectedDayId] = React.useState<string>(todayIso)
  const [weekData, setWeekData] = React.useState<Map<string, WeekDayData>>(new Map())
  const [recs, setRecs] = React.useState<Recommendation[]>([])

  const selectedDate = dateForSelectedDay(selectedDayId, weekDays)
  const selectedDayData = weekData.get(selectedDate)
  const riskScore = selectedDayData?.risk?.score ?? null
  const riskLabel = selectedDayData?.risk?.label ?? "No prediction"
  const activeRiskFactors = React.useMemo(
    () =>
      (selectedDayData?.activeRiskFactors ?? []).map((f) => ({
        id: f.id,
        label: f.label,
        icon: ICONS[f.iconKey] ?? Wind,
      })),
    [selectedDayData?.activeRiskFactors]
  )
  const dayRiskMap = React.useMemo(() => {
    const m: Record<string, { level: string; label: string }> = {}
    weekData.forEach((data, date) => {
      m[date] = { level: data.risk.level, label: data.risk.label }
    })
    return m
  }, [weekData])

  React.useEffect(() => {
    setSelectedDayId((prev) => (weekDays.some((d) => d.id === prev) ? prev : weekDays[0]?.id ?? prev))
  }, [weekDays])

  React.useEffect(() => {
    const controller = new AbortController()
    const start = weekDays[0]?.id
    if (!start) return
    const locationParam = location ? `&location=${encodeURIComponent(location)}` : ""
    fetch(`/api/week?start=${encodeURIComponent(start)}&days=7${locationParam}`, { signal: controller.signal })
      .then((r) => (r.ok ? r.json() : null))
      .then((json: { days?: WeekDayData[] } | null) => {
        const days = json?.days ?? []
        const map = new Map<string, WeekDayData>()
        days.forEach((d) => {
          if (d?.date) map.set(d.date, d)
        })
        setWeekData(map)
      })
      .catch(() => setWeekData(new Map()))
    return () => controller.abort()
  }, [weekDays, location])

  React.useEffect(() => {
    if (!selectedDayData?.risk?.level) return
    const controller = new AbortController()
    fetch(
      `/api/recommendations?date=${encodeURIComponent(selectedDate)}&riskLevel=${encodeURIComponent(
        selectedDayData.risk.level
      )}`,
      { signal: controller.signal }
    )
      .then((r) => (r.ok ? r.json() : null))
      .then((data: ApiRecommendationsResponse | null) => {
        if (data?.recommendations) setRecs(data.recommendations)
      })
      .catch(() => {})
    return () => controller.abort()
  }, [selectedDate, selectedDayData?.risk?.level])

  return (
    <div className={layout.pageBg}>
      <main className={layout.container}>
        <div className={cn("flex flex-col", spacing.sectionGap)}>
          <Header title="Wheeze-Wise" />

          <RiskTabs value={tab} onValueChange={setTab} />

          {locationStatus === "loading" && (
            <p className="text-muted-foreground text-sm">Getting your location…</p>
          )}
          {(locationStatus === "denied" || locationStatus === "error" || locationStatus === "unavailable") && (
            <div className="flex flex-wrap items-center gap-2 text-sm">
              <span className="text-muted-foreground">
                {locationStatus === "denied"
                  ? "Location access was denied. Allow location to see risk for your area."
                  : "Location unavailable."}
              </span>
              <Button type="button" variant="outline" size="sm" onClick={requestLocation}>
                Try again
              </Button>
            </div>
          )}

          <DateStrip
            days={weekDays}
            selectedId={selectedDayId}
            onSelect={(id) => setSelectedDayId(id)}
            dayRiskMap={dayRiskMap}
          />

          {/* Mobile-first: single column; Desktop: use space with a 2-col grid */}
          <div className="grid min-w-0 gap-6 sm:gap-8 md:grid-cols-2 md:items-start">
            <div className="min-w-0 space-y-6 sm:space-y-8">
              <RiskGauge value={riskScore} label={riskLabel} />
              <RiskFactors items={activeRiskFactors} />
            </div>

            <div className="min-w-0 space-y-6 sm:space-y-8">
              <Recommendations items={recs} />
            </div>
          </div>

          <div className="sticky bottom-0 left-0 right-0 flex justify-center pb-safe pt-4 md:static md:pb-0">
            <Button
              size="pill"
              className="min-h-11 w-full touch-manipulation md:min-h-0 md:w-fit md:px-12"
              onClick={() => {
                // Check authentication before navigating
                if (status === "loading") {
                  return
                }
                
                if (!session) {
                  // Not authenticated, redirect to sign-in
                  signIn("google", {
                    callbackUrl: "/breathe-well/personalized",
                  })
                } else {
                  // Authenticated, navigate to personalized page
                  router.push("/breathe-well/personalized")
                }
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


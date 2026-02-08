"use client"

import * as React from "react"
import { Droplets, Sprout, Thermometer, Wind } from "lucide-react"

import { Button } from "@/components/ui/button"
import { useRouter } from "next/navigation"
import { useSession, signIn } from "next-auth/react"

import { DateStrip } from "./DateStrip"
import { useGeolocation } from "./useGeolocation"
import { Recommendations } from "./Recommendations"
import { RiskFactors } from "./RiskFactors"
import { RiskGauge } from "./RiskGauge"
import { getWeekDaysFromToday, type DayItem, type Recommendation, type RiskFactor } from "./mockData"

type ApiRiskLevel = "low" | "moderate" | "high"
type ApiRiskFactor = {
  id: string
  label: string
  iconKey: "sprout" | "wind" | "thermometer" | "droplets"
}
type ApiDaily = {
  date?: string
  location_id?: string
  AQI?: number | null
  PM2_5_max?: number | null
  PM2_5_mean?: number | null
  day_of_week?: string
  humidity?: number | null
  latitude?: number | null
  longitude?: number | null
  month?: number | null
  pollen_grass?: number | null
  pollen_tree?: number | null
  pollen_weed?: number | null
  pressure?: number | null
  rain?: number | null
  season?: string
  temp_max?: number | null
  temp_min?: number | null
  wind?: number | null
  zip_code?: string | null
}
type ApiRiskResponse = {
  date: string
  risk: { score: number; level: ApiRiskLevel; label: string }
  activeRiskFactors: ApiRiskFactor[]
  daily?: ApiDaily
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

/** Use selected day id as date when it is YYYY-MM-DD, else from week day or today. */
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

type WeekDayData = {
  date: string
  risk: { score: number; level: string; label: string }
  activeRiskFactors: ApiRiskFactor[]
  daily?: ApiDaily | null
}

export function EnvironmentalRiskContent() {
  const router = useRouter()
  const { data: session, status } = useSession()
  const { location, status: locationStatus, requestLocation } = useGeolocation()
  const weekDays = React.useMemo(() => getWeekDaysFromToday(), [])
  const todayIso = weekDays[0]?.id ?? new Date().toISOString().slice(0, 10)
  const [selectedDayId, setSelectedDayId] = React.useState<string>(todayIso)

  const [weekData, setWeekData] = React.useState<Map<string, WeekDayData>>(new Map())
  const [weekLoading, setWeekLoading] = React.useState(true)
  const [fromModel, setFromModel] = React.useState<boolean | null>(null)
  const [recs, setRecs] = React.useState<Recommendation[]>([])
  const [recsLoading, setRecsLoading] = React.useState(false)

  const selectedDate = dateForSelectedDay(selectedDayId, weekDays)
  const selectedDayData = weekData.get(selectedDate)

  const riskScore = selectedDayData?.risk?.score ?? null
  const riskLabel = selectedDayData?.risk?.label ?? "No prediction"
  const activeRiskFactors: RiskFactor[] = React.useMemo(
    () =>
      (selectedDayData?.activeRiskFactors ?? []).map((f) => ({
        id: f.id,
        label: f.label,
        icon: ICONS[f.iconKey as ApiRiskFactor["iconKey"]] ?? Wind,
      })),
    [selectedDayData?.activeRiskFactors]
  )
  const daily = selectedDayData?.daily ?? null

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
    async function loadWeek() {
      if (!start) return
      setWeekLoading(true)
      try {
        const locationParam = location ? `&location=${encodeURIComponent(location)}` : ""
        const res = await fetch(`/api/week?start=${encodeURIComponent(start)}&days=7${locationParam}`, {
          signal: controller.signal,
        })
        if (!res.ok) {
          setWeekData(new Map())
          return
        }
        const json = (await res.json()) as { start?: string; days?: WeekDayData[]; fromModel?: boolean }
        const days = json.days ?? []
        const map = new Map<string, WeekDayData>()
        days.forEach((d) => {
          if (d?.date) map.set(d.date, d)
        })
        setWeekData(map)
        setFromModel(json.fromModel ?? null)
      } catch {
        setWeekData(new Map())
      } finally {
        setWeekLoading(false)
      }
    }
    void loadWeek()
    return () => controller.abort()
  }, [weekDays, location])

  React.useEffect(() => {
    if (!selectedDayData?.risk?.level) return
    const controller = new AbortController()
    setRecsLoading(true)
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
      .finally(() => setRecsLoading(false))
    return () => controller.abort()
  }, [selectedDate, selectedDayData?.risk?.level])

  return (
    <>
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
      <h2 className="text-sm font-medium text-muted-foreground">
        {weekLoading
          ? "Next 7 days — running model…"
          : fromModel === true
            ? "Next 7 days — risk forecast from model"
            : fromModel === false
              ? "Next 7 days — risk forecast (estimated)"
              : "Next 7 days — risk forecast"}
      </h2>
      <DateStrip
        days={weekDays}
        selectedId={selectedDayId}
        onSelect={(id) => setSelectedDayId(id)}
        dayRiskMap={dayRiskMap}
      />
      {weekLoading && (
        <p className="text-muted-foreground text-sm">Loading predictions (model compiling)…</p>
      )}

      {/* Mobile-first: single column; Desktop: use space with a 2-col grid */}
      <div className="grid gap-8 md:grid-cols-2 md:items-start">
        <div className="space-y-8">
          {recsLoading && (
            <p className="text-muted-foreground text-sm">Loading recommendations…</p>
          )}
          <RiskGauge value={riskScore} label={riskLabel} />
          <RiskFactors items={activeRiskFactors} />
          {selectedDayData != null && (
            <div className="rounded-2xl border bg-card p-4 text-sm">
              <h3 className="mb-2 font-medium">Data for this day</h3>
              {fromModel === false && (
                <p className="text-muted-foreground mb-2 text-xs">Estimated. Run the model (see below) for real environmental data.</p>
              )}
              {daily && (daily.day_of_week != null || daily.season != null || daily.AQI != null || daily.PM2_5_mean != null || daily.temp_min != null || daily.humidity != null) ? (
                <dl className="grid grid-cols-2 gap-x-4 gap-y-1">
                  {daily.AQI != null && <><dt className="text-muted-foreground">AQI</dt><dd>{daily.AQI}</dd></>}
                  {daily.PM2_5_mean != null && <><dt className="text-muted-foreground">PM2.5 mean</dt><dd>{daily.PM2_5_mean}</dd></>}
                  {daily.PM2_5_max != null && <><dt className="text-muted-foreground">PM2.5 max</dt><dd>{daily.PM2_5_max}</dd></>}
                  {daily.day_of_week != null && <><dt className="text-muted-foreground">Day</dt><dd>{daily.day_of_week}</dd></>}
                  {daily.season != null && <><dt className="text-muted-foreground">Season</dt><dd>{daily.season}</dd></>}
                  {(daily.temp_min != null || daily.temp_max != null) && (
                    <><dt className="text-muted-foreground">Temp</dt><dd>{[daily.temp_min, daily.temp_max].filter((t) => t != null).join("–")} °C</dd></>
                  )}
                  {daily.humidity != null && <><dt className="text-muted-foreground">Humidity</dt><dd>{daily.humidity}%</dd></>}
                  {(daily.pollen_tree != null || daily.pollen_grass != null || daily.pollen_weed != null) && (
                    <><dt className="text-muted-foreground">Pollen</dt><dd>Tree {daily.pollen_tree ?? "—"} / Grass {daily.pollen_grass ?? "—"} / Weed {daily.pollen_weed ?? "—"}</dd></>
                  )}
                </dl>
              ) : (
                <p className="text-muted-foreground text-xs">No environmental data for this day.</p>
              )}
            </div>
          )}
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
    </>
  )
}

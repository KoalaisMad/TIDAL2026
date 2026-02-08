"use client"

import * as React from "react"
import { Droplets, Sprout, Thermometer, Wind } from "lucide-react"

import { Button } from "@/components/ui/button"
import { useRouter } from "next/navigation"
import { useSession, signIn } from "next-auth/react"

import { AllergyChatbot } from "./AllergyChatbot"
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

function celsiusToFahrenheit(c: number): number {
  return Math.round((c * 9) / 5 + 32)
}

type PollenSeverityLevel = "Low" | "Moderate" | "High" | "—"

/** Map numeric pollen index to a severity label (handles 0–5 and 0–50 scales). */
function pollenSeverity(value: number | null | undefined): PollenSeverityLevel {
  if (value == null || Number.isNaN(value)) return "—"
  const n = value <= 12 ? value : value / 5
  if (n <= 3) return "Low"
  if (n <= 7) return "Moderate"
  return "High"
}

function pollenSeverityClass(level: PollenSeverityLevel): string {
  if (level === "Low") return "text-emerald-600 dark:text-emerald-400"
  if (level === "Moderate") return "text-amber-600 dark:text-amber-400"
  if (level === "High") return "text-destructive"
  return "text-muted-foreground"
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
    const body = {
      date: selectedDate,
      riskLevel: selectedDayData.risk.level,
      daily: selectedDayData.daily ?? undefined,
      activeRiskFactors: selectedDayData.activeRiskFactors?.map(({ id, label }) => ({ id, label })),
    }
    fetch("/api/recommendations", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
      signal: controller.signal,
    })
      .then((r) => (r.ok ? r.json() : null))
      .then((data: ApiRecommendationsResponse | null) => {
        if (data?.recommendations) setRecs(data.recommendations)
      })
      .catch(() => {})
      .finally(() => setRecsLoading(false))
    return () => controller.abort()
  }, [selectedDate, selectedDayData?.risk?.level, selectedDayData?.daily, selectedDayData?.activeRiskFactors])

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
              <h3 className="mb-3 font-medium">Conditions for this day</h3>
              {fromModel === false && (
                <p className="text-muted-foreground mb-3 text-xs">Estimated. Run the model (see below) for real environmental data.</p>
              )}
              {daily && (daily.day_of_week != null || daily.season != null || daily.AQI != null || daily.PM2_5_mean != null || daily.temp_min != null || daily.humidity != null) ? (
                <ul className="space-y-3">
                  {daily.day_of_week != null && (
                    <li className="flex justify-between gap-4 border-b border-border/60 pb-2">
                      <span className="text-muted-foreground">Day</span>
                      <span className="font-medium capitalize">{daily.day_of_week}</span>
                    </li>
                  )}
                  {daily.season != null && (
                    <li className="flex justify-between gap-4 border-b border-border/60 pb-2">
                      <span className="text-muted-foreground">Season</span>
                      <span className="font-medium capitalize">{daily.season}</span>
                    </li>
                  )}
                  {(daily.temp_min != null || daily.temp_max != null) && (
                    <li className="flex justify-between gap-4 border-b border-border/60 pb-2">
                      <span className="text-muted-foreground">Temperature</span>
                      <span className="font-medium">
                        {[daily.temp_min, daily.temp_max]
                          .filter((t): t is number => t != null)
                          .map(celsiusToFahrenheit)
                          .join("–")}
                        °F
                      </span>
                    </li>
                  )}
                  {daily.AQI != null && (
                    <li className="flex justify-between gap-4 border-b border-border/60 pb-2">
                      <span className="text-muted-foreground">Air quality index</span>
                      <span className="font-medium">{daily.AQI}</span>
                    </li>
                  )}
                  {(daily.PM2_5_mean != null || daily.PM2_5_max != null) && (
                    <li className="flex justify-between gap-4 border-b border-border/60 pb-2">
                      <span className="text-muted-foreground">Particle pollution (PM2.5)</span>
                      <span className="font-medium">
                        {daily.PM2_5_mean != null && daily.PM2_5_max != null
                          ? `Avg ${daily.PM2_5_mean.toFixed(1)}, high ${daily.PM2_5_max.toFixed(1)}`
                          : daily.PM2_5_mean != null
                            ? `Avg ${daily.PM2_5_mean.toFixed(1)}`
                            : daily.PM2_5_max != null
                              ? `High ${daily.PM2_5_max.toFixed(1)}`
                              : "—"}
                      </span>
                    </li>
                  )}
                  {daily.humidity != null && (
                    <li className="flex justify-between gap-4 border-b border-border/60 pb-2">
                      <span className="text-muted-foreground">Humidity</span>
                      <span className="font-medium">{Math.round(daily.humidity)}%</span>
                    </li>
                  )}
                  {(daily.pollen_tree != null || daily.pollen_grass != null || daily.pollen_weed != null) && (
                    <li className="flex flex-col gap-1.5 border-b border-border/60 pb-2">
                      <span className="text-muted-foreground">Pollen levels</span>
                      <span className="font-medium">
                        Tree <span className={pollenSeverityClass(pollenSeverity(daily.pollen_tree))}>{pollenSeverity(daily.pollen_tree)}</span>
                        {" · "}
                        Grass <span className={pollenSeverityClass(pollenSeverity(daily.pollen_grass))}>{pollenSeverity(daily.pollen_grass)}</span>
                        {" · "}
                        Weed <span className={pollenSeverityClass(pollenSeverity(daily.pollen_weed))}>{pollenSeverity(daily.pollen_weed)}</span>
                      </span>
                    </li>
                  )}
                </ul>
              ) : (
                <p className="text-muted-foreground text-xs">No environmental data for this day.</p>
              )}
            </div>
          )}
        </div>

        <div className="space-y-8">
          <Recommendations items={recs} />
          <AllergyChatbot weekData={weekData} weekStart={weekDays[0]?.id} />
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

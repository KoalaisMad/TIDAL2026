"use client"

import * as React from "react"

import { Card } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { useRouter } from "next/navigation"
import { DateStrip } from "./DateStrip"
import { PredictionsLoadingIndicator } from "./PredictionsLoadingIndicator"
import { RiskGauge } from "./RiskGauge"
import { getWeekDaysFromToday } from "./mockData"

/** Daily check-in: ordinal 0–3 and exercise minutes */
export interface DailyCheckIn {
  wheeze: number
  cough: number
  chestTightness: number
  exerciseMinutes: number
}

const ORDINAL_OPTIONS = [0, 1, 2, 3] as const

type WeekDayData = {
  date: string
  risk: { score: number; level: string; label: string }
  activeRiskFactors: Array<{ id: string; label: string; iconKey: string }>
}

export function PersonalizedRiskContent() {
  const router = useRouter()
  const weekDays = React.useMemo(() => getWeekDaysFromToday(), [])
  const todayIso = weekDays[0]?.id ?? new Date().toISOString().slice(0, 10)

  const [dailyCheckIn, setDailyCheckIn] = React.useState<DailyCheckIn>({
    wheeze: 0,
    cough: 0,
    chestTightness: 0,
    exerciseMinutes: 0,
  })
  const [checkInSaved, setCheckInSaved] = React.useState(false)
  const [checkInSaving, setCheckInSaving] = React.useState(false)

  // Personalized 7-day predictions from pgood model + saved profile & check-ins (predict_personalized.py)
  const [weekData, setWeekData] = React.useState<Map<string, WeekDayData>>(new Map())
  const [fromModel, setFromModel] = React.useState<boolean | null>(null)
  const [weekLoading, setWeekLoading] = React.useState(true)
  const [selectedDayId, setSelectedDayId] = React.useState<string>(todayIso)

  const selectedDate = React.useMemo(() => {
    if (/^\d{4}-\d{2}-\d{2}$/.test(selectedDayId)) return selectedDayId
    const day = weekDays.find((d) => d.id === selectedDayId)
    return day?.date ?? selectedDayId
  }, [selectedDayId, weekDays])
  const selectedDayData = weekData.get(selectedDate)
  const riskScore = selectedDayData?.risk?.score ?? null
  const riskLabel = selectedDayData?.risk?.label ?? "No prediction"
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
    async function loadPersonalized() {
      if (!start) return
      setWeekLoading(true)
      try {
        const res = await fetch(`/api/risk/personalized`, { signal: controller.signal })
        if (!res.ok) {
          setWeekData(new Map())
          setFromModel(false)
          return
        }
        const json = (await res.json()) as { start?: string; days?: WeekDayData[]; fromModel?: boolean }
        setFromModel(json.fromModel === true)
        const days = json.days ?? []
        // Always show 7 days (from pgood model or estimated fallback) so the strip and gauge have values
        const map = new Map<string, WeekDayData>()
        days.forEach((d) => {
          if (d?.date) map.set(d.date, d)
        })
        setWeekData(map)
      } catch {
        setWeekData(new Map())
        setFromModel(false)
      } finally {
        setWeekLoading(false)
      }
    }
    void loadPersonalized()
    return () => controller.abort()
  }, [weekDays])

  React.useEffect(() => {
    const onProfileUpdated = () => {
      setWeekLoading(true)
      fetch("/api/risk/personalized")
        .then((res) => (res.ok ? res.json() : null))
        .then((json: { days?: WeekDayData[]; fromModel?: boolean } | null) => {
          setFromModel(json?.fromModel === true ?? false)
          const days = json?.days ?? []
          const map = new Map<string, WeekDayData>()
          days.forEach((d) => { if (d?.date) map.set(d.date, d) })
          setWeekData(map)
        })
        .finally(() => setWeekLoading(false))
    }
    window.addEventListener("profile-updated", onProfileUpdated)
    return () => window.removeEventListener("profile-updated", onProfileUpdated)
  }, [])

  const saveDailyCheckIn = async () => {
    setCheckInSaving(true)
    setCheckInSaved(false)
    try {
      const res = await fetch("/api/users/check-in", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          wheeze: dailyCheckIn.wheeze,
          cough: dailyCheckIn.cough,
          chestTightness: dailyCheckIn.chestTightness,
          exerciseMinutes: dailyCheckIn.exerciseMinutes,
        }),
      })
      if (!res.ok) throw new Error("Failed to save check-in")
      setCheckInSaved(true)
      setTimeout(() => setCheckInSaved(false), 3000)
    } catch {
      // show error if needed
    } finally {
      setCheckInSaving(false)
    }
  }

  return (
    <>
      {/* Personalized 7-day predictions from pgood model + profile & check-ins */}
      <h2 className="text-sm font-medium text-muted-foreground">
        {weekLoading
          ? "Next 7 days — loading personalized risk…"
          : fromModel === true
            ? "Next 7 days — personalized risk (pgood model, your profile & check-ins)"
            : fromModel === false
              ? "Next 7 days — personalized risk (estimated)"
              : "Next 7 days — personalized risk"}
      </h2>
      <DateStrip
        days={weekDays}
        selectedId={selectedDayId}
        onSelect={(id) => setSelectedDayId(id)}
        dayRiskMap={dayRiskMap}
      />
      {(weekLoading || riskScore === null) ? (
        <PredictionsLoadingIndicator
          message={weekLoading ? "Loading personalized risk…" : "Loading prediction…"}
          submessage={
            weekLoading
              ? "Using your profile and check-ins with the pgood model"
              : "Getting risk for this day"
          }
          showGaugeSkeleton
        />
      ) : (
        <RiskGauge value={riskScore} label={riskLabel} />
      )}

      {/* Short daily check-in (10–15 seconds) */}
      <Card className="p-6">
        <div className="space-y-4">
          <h2 className="text-xl font-bold">Daily check-in</h2>
          <p className="text-sm text-muted-foreground">
            Quick symptom and activity log (0 = none, 3 = severe).
          </p>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <div className="space-y-1.5">
              <label className="text-sm font-medium">Wheeze (0–3)</label>
              <Select
                value={String(dailyCheckIn.wheeze)}
                onValueChange={(v) =>
                  setDailyCheckIn((prev) => ({ ...prev, wheeze: Number(v) }))
                }
              >
                <SelectTrigger className="bg-white">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {ORDINAL_OPTIONS.map((n) => (
                    <SelectItem key={n} value={String(n)}>
                      {n}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-1.5">
              <label className="text-sm font-medium">Cough (0–3)</label>
              <Select
                value={String(dailyCheckIn.cough)}
                onValueChange={(v) =>
                  setDailyCheckIn((prev) => ({ ...prev, cough: Number(v) }))
                }
              >
                <SelectTrigger className="bg-white">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {ORDINAL_OPTIONS.map((n) => (
                    <SelectItem key={n} value={String(n)}>
                      {n}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-1.5">
              <label className="text-sm font-medium">Chest tightness (0–3)</label>
              <Select
                value={String(dailyCheckIn.chestTightness)}
                onValueChange={(v) =>
                  setDailyCheckIn((prev) => ({ ...prev, chestTightness: Number(v) }))
                }
              >
                <SelectTrigger className="bg-white">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {ORDINAL_OPTIONS.map((n) => (
                    <SelectItem key={n} value={String(n)}>
                      {n}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-1.5">
              <label className="text-sm font-medium">Exercise / outdoor time (min)</label>
              <Input
                type="number"
                min={0}
                max={1440}
                placeholder="e.g. 45"
                value={dailyCheckIn.exerciseMinutes || ""}
                onChange={(e) => {
                  const v = e.target.value === "" ? 0 : parseInt(e.target.value, 10)
                  setDailyCheckIn((prev) => ({ ...prev, exerciseMinutes: isNaN(v) ? 0 : Math.max(0, v) }))
                }}
                className="bg-white"
              />
            </div>
          </div>
          <div className="mt-4 flex items-center gap-3">
            <Button
              type="button"
              size="pill"
              onClick={saveDailyCheckIn}
              disabled={checkInSaving}
            >
              {checkInSaved ? "Saved!" : checkInSaving ? "Saving…" : "Save check-in"}
            </Button>
            {checkInSaved && (
              <span className="text-sm text-emerald-600 dark:text-emerald-400">
                Check-in saved.
              </span>
            )}
          </div>
        </div>
      </Card>

      <div className="sticky bottom-0 left-0 right-0 flex justify-center pb-safe pt-4 md:static md:pb-0">
        <Button
          size="pill"
          variant="outline"
          className="min-h-11 w-full touch-manipulation md:min-h-0 md:w-fit md:px-12"
          onClick={() => {
            router.push("/breathe-well/environmental")
          }}
        >
          Back to Environmental Risk
        </Button>
      </div>
    </>
  )
}

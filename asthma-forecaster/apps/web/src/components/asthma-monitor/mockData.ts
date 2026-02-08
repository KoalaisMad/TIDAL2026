import type { LucideIcon } from "lucide-react"
import { Droplets, Sprout, Thermometer, Wind } from "lucide-react"

export type DayItem = {
  id: string
  dow: string
  dayOfMonth: number
  /** ISO date YYYY-MM-DD for API calls */
  date?: string
}

/** Format date as YYYY-MM-DD in local time (so strip and API keys match). */
function toLocalDateStr(d: Date): string {
  const y = d.getFullYear()
  const m = String(d.getMonth() + 1).padStart(2, "0")
  const day = String(d.getDate()).padStart(2, "0")
  return `${y}-${m}-${day}`
}

/** Build the next 7 days from today for dynamic calendar strip. id = local YYYY-MM-DD. */
export function getWeekDaysFromToday(): DayItem[] {
  const days: DayItem[] = []
  const dowShort = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]
  for (let i = 0; i < 7; i++) {
    const d = new Date()
    d.setDate(d.getDate() + i)
    const dateStr = toLocalDateStr(d)
    days.push({
      id: dateStr,
      dow: dowShort[d.getDay()],
      dayOfMonth: d.getDate(),
      date: dateStr,
    })
  }
  return days
}

export type RiskFactor = {
  id: string
  label: string
  icon: LucideIcon
}

export type Recommendation = {
  id: string
  title: string
  description: string
}

/** Static fallback when dynamic week not used. */
export const weekDays: DayItem[] = [
  { id: "sun", dow: "Sun", dayOfMonth: 1 },
  { id: "mon", dow: "Mon", dayOfMonth: 2 },
  { id: "tue", dow: "Tue", dayOfMonth: 3 },
  { id: "wed", dow: "Wed", dayOfMonth: 4 },
  { id: "thu", dow: "Thu", dayOfMonth: 5 },
  { id: "fri", dow: "Fri", dayOfMonth: 6 },
  { id: "sat", dow: "Sat", dayOfMonth: 7 },
] as const

// TODO(api): Replace with dynamic risk factors from backend + thresholds.
export const riskFactors: RiskFactor[] = [
  { id: "pollen", label: "High Pollen", icon: Sprout },
  { id: "air", label: "Poor Air Quality", icon: Wind },
  { id: "temp", label: "Cold Temperature", icon: Thermometer },
  { id: "humidity", label: "High Humidity", icon: Droplets },
] as const

// TODO(api): Replace with personalized recommendations from backend/LLM.
export const recommendations: Recommendation[] = [
  {
    id: "limit-outdoor",
    title: "Limit Outdoor Activities",
    description:
      "Pollen levels are high today. Consider staying indoors during peak hours.",
  },
  {
    id: "inhaler",
    title: "Keep Rescue Inhaler Nearby",
    description:
      "Your risk is elevated. Make sure your quick-relief inhaler is accessible.",
  },
  {
    id: "monitor",
    title: "Monitor Symptoms Closely",
    description:
      "Track any wheezing, coughing, or chest tightness throughout the day.",
  },
  {
    id: "air-quality",
    title: "Check Air Quality Before Exercise",
    description:
      "Air quality is poor. Choose early morning or evening for outdoor activities.",
  },
  {
    id: "windows",
    title: "Close Windows Today",
    description:
      "Keep windows closed to prevent outdoor allergens from entering your home.",
  },
] as const


export type RiskLevel = "low" | "moderate" | "high"

export type ApiRiskFactor = {
  id: string
  label: string
  /**
   * Client can map this to an icon component.
   * Keep it serializable (no component/functions in API responses).
   */
  iconKey: "sprout" | "wind" | "thermometer" | "droplets"
}

export type ApiRecommendation = {
  id: string
  title: string
  description: string
}

// Mirrors the current dummy UI content (see `src/components/asthma-monitor/mockData.ts`)
export const DUMMY_ACTIVE_RISK_FACTORS: ApiRiskFactor[] = [
  { id: "pollen", label: "High Pollen", iconKey: "sprout" },
  { id: "air", label: "Poor Air Quality", iconKey: "wind" },
  { id: "temp", label: "Cold Temperature", iconKey: "thermometer" },
  { id: "humidity", label: "High Humidity", iconKey: "droplets" },
] as const

export const DUMMY_RECOMMENDATIONS: ApiRecommendation[] = [
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

export function isRiskLevel(value: string | null): value is RiskLevel {
  return value === "low" || value === "moderate" || value === "high"
}

export function isIsoDate(value: string | null): value is string {
  // Simple stub validation: YYYY-MM-DD
  return !!value && /^\d{4}-\d{2}-\d{2}$/.test(value)
}


import { NextResponse } from "next/server"

import {
  DUMMY_RECOMMENDATIONS,
  isIsoDate,
  isRiskLevel,
  type ApiRecommendation,
  type RiskLevel,
} from "../_mock"

const GEMINI_MODEL = "gemini-2.5-flash"
const GEMINI_URL = `https://generativelanguage.googleapis.com/v1beta/models/${GEMINI_MODEL}:generateContent`

type DailyContext = {
  date?: string
  day_of_week?: string
  season?: string
  AQI?: number | null
  PM2_5_mean?: number | null
  PM2_5_max?: number | null
  temp_min?: number | null
  temp_max?: number | null
  humidity?: number | null
  pollen_tree?: number | null
  pollen_grass?: number | null
  pollen_weed?: number | null
  [key: string]: unknown
}

type RecommendationsContext = {
  daily?: DailyContext | null
  activeRiskFactors?: Array<{ id: string; label: string }>
}

function buildRecommendationsPrompt(
  date: string,
  riskLevel: RiskLevel,
  context: RecommendationsContext | null
): string {
  const parts = [
    `Generate 4 to 6 short, practical allergy and asthma management recommendations for this day:`,
    `- Date: ${date}`,
    `- Risk level: ${riskLevel}`,
  ]
  if (context?.daily) {
    const d = context.daily
    parts.push(
      "- Environmental data:",
      `  AQI: ${d.AQI ?? "—"}, PM2.5 mean: ${d.PM2_5_mean ?? "—"}, temp: ${d.temp_min ?? "—"}–${d.temp_max ?? "—"} °C, humidity: ${d.humidity ?? "—"}%`,
      `  Pollen: tree ${d.pollen_tree ?? "—"}, grass ${d.pollen_grass ?? "—"}, weed ${d.pollen_weed ?? "—"}`
    )
  }
  if (context?.activeRiskFactors?.length) {
    parts.push(
      `- Active risk factors: ${context.activeRiskFactors.map((f) => f.label).join(", ")}`
    )
  }
  parts.push(
    "",
    "Reply with only a JSON array of 4 to 6 recommendation objects. Each object must have: \"id\" (kebab-case, e.g. limit-outdoor), \"title\" (short string), \"description\" (1-2 sentences). Output no other text or markdown—only the JSON array."
  )
  return parts.join("\n")
}

function extractJsonArray(text: string): unknown[] | null {
  let raw = (text ?? "").trim()
  // Strip markdown code block if present
  const codeBlock = raw.match(/```(?:json)?\s*([\s\S]*?)```/)
  if (codeBlock) raw = codeBlock[1].trim()
  // Find first [ or { to skip any leading prose
  const arrayStart = raw.indexOf("[")
  if (arrayStart >= 0) raw = raw.slice(arrayStart)
  let parsed: unknown
  try {
    parsed = JSON.parse(raw)
  } catch {
    return null
  }
  if (Array.isArray(parsed)) return parsed
  if (parsed && typeof parsed === "object" && !Array.isArray(parsed)) {
    const obj = parsed as Record<string, unknown>
    const arr = obj.recommendations ?? obj.items ?? obj.recs
    if (Array.isArray(arr)) return arr
  }
  return null
}

function parseRecommendationsFromGemini(text: string): ApiRecommendation[] {
  const arr = extractJsonArray(text)
  if (!arr || arr.length === 0) return []
  const out: ApiRecommendation[] = []
  for (let i = 0; i < arr.length; i++) {
    const item = arr[i]
    if (item == null || typeof item !== "object") continue
    const o = item as Record<string, unknown>
    const title = typeof o.title === "string" ? o.title.trim() : ""
    const description = typeof o.description === "string" ? o.description.trim() : ""
    if (!title || !description) continue
    const rawId = typeof o.id === "string" ? o.id : ""
    const id =
      rawId.replace(/\s+/g, "-").toLowerCase().replace(/[^a-z0-9-]/g, "") ||
      `rec-${i}`
    out.push({ id: id || `rec-${i}`, title, description })
  }
  return out
}

async function generateRecommendationsWithGemini(
  date: string,
  riskLevel: RiskLevel,
  context: RecommendationsContext | null
): Promise<ApiRecommendation[]> {
  const key = process.env.GEMINI_KEY ?? process.env.GEMINI_API_KEY
  if (!key?.trim()) {
    console.error("[api/recommendations] GEMINI_KEY (or GEMINI_API_KEY) not set in environment")
    return []
  }

  const prompt = buildRecommendationsPrompt(date, riskLevel, context)
  const payload = {
    contents: [{ parts: [{ text: prompt }] }],
    generationConfig: {
      temperature: 0.5,
      maxOutputTokens: 1024,
      thinkingConfig: { thinkingBudget: 0 },
    },
  }
  const url = `${GEMINI_URL}?key=${encodeURIComponent(key)}`
  let res: Response
  try {
    res = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    })
  } catch {
    return []
  }
  const data = await res.json().catch(() => ({}))
  if (!res.ok) {
    console.error("[api/recommendations] Gemini error:", res.status, data?.error?.message ?? data?.error ?? "")
    return []
  }
  const parts = data?.candidates?.[0]?.content?.parts
  let text = ""
  if (Array.isArray(parts) && parts.length > 0) {
    // Use last part that has text (Gemini 2.5 may return thinking first, then the JSON)
    for (let i = parts.length - 1; i >= 0; i--) {
      const p = parts[i]
      const t = typeof p === "string" ? p : (p && (p as { text?: string }).text)
      if (typeof t === "string" && t.trim()) {
        text = t
        break
      }
    }
    if (!text && parts.length > 0) {
      const first = parts[0]
      text = typeof first === "string" ? first : (first && (first as { text?: string }).text) ?? ""
    }
  }
  if (typeof text !== "string" || !text.trim()) return []
  try {
    const recs = parseRecommendationsFromGemini(text)
    return recs.length > 0 ? recs : []
  } catch (e) {
    console.error("[api/recommendations] Parse error:", (e as Error).message, "text length:", text.length)
    return []
  }
}

async function getRecommendations(
  date: string,
  riskLevel: RiskLevel,
  context: RecommendationsContext | null
): Promise<ApiRecommendation[]> {
  const generated = await generateRecommendationsWithGemini(date, riskLevel, context)
  return generated.length > 0 ? generated : [...DUMMY_RECOMMENDATIONS]
}

export async function GET(request: Request) {
  const url = new URL(request.url)
  const date = url.searchParams.get("date")
  const riskLevel = url.searchParams.get("riskLevel")

  if (!isIsoDate(date)) {
    return NextResponse.json(
      { error: "Missing or invalid `date` (expected YYYY-MM-DD)." },
      { status: 400 }
    )
  }

  if (!isRiskLevel(riskLevel)) {
    return NextResponse.json(
      {
        error:
          "Missing or invalid `riskLevel` (expected one of: low, moderate, high).",
      },
      { status: 400 }
    )
  }

  const recommendations = await getRecommendations(date, riskLevel, null)
  return NextResponse.json({
    date,
    riskLevel,
    recommendations,
  })
}

export async function POST(request: Request) {
  let body: {
    date?: string
    riskLevel?: string
    daily?: DailyContext | null
    activeRiskFactors?: Array<{ id: string; label: string }>
  }
  try {
    body = await request.json()
  } catch {
    return NextResponse.json(
      { error: "Invalid JSON body." },
      { status: 400 }
    )
  }

  const date = body?.date ?? null
  const riskLevel = body?.riskLevel ?? null

  if (!isIsoDate(date)) {
    return NextResponse.json(
      { error: "Missing or invalid `date` (expected YYYY-MM-DD)." },
      { status: 400 }
    )
  }

  if (!isRiskLevel(riskLevel)) {
    return NextResponse.json(
      {
        error:
          "Missing or invalid `riskLevel` (expected one of: low, moderate, high).",
      },
      { status: 400 }
    )
  }

  const context: RecommendationsContext | null =
    body?.daily != null || (body?.activeRiskFactors?.length ?? 0) > 0
      ? {
          daily: body.daily ?? null,
          activeRiskFactors: body.activeRiskFactors ?? undefined,
        }
      : null

  const recommendations = await getRecommendations(date, riskLevel, context)
  return NextResponse.json({
    date,
    riskLevel,
    recommendations,
  })
}

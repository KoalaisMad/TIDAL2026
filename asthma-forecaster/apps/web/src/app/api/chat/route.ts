import { NextResponse } from "next/server"

const GEMINI_MODEL = "gemini-2.5-flash"
const GEMINI_URL = `https://generativelanguage.googleapis.com/v1beta/models/${GEMINI_MODEL}:generateContent`

type WeekDayContext = {
  date: string
  risk: { score: number; level: string; label: string }
  activeRiskFactors?: Array<{ id: string; label: string; iconKey?: string }>
  daily?: {
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
}

function buildSystemInstruction(weekContext: {
  start?: string
  days: WeekDayContext[]
} | null): string {
  const base = `You are a helpful allergy and asthma assistant for the Wheeze-Wise app. You help users understand their allergy and asthma risk for the coming days and how to respond. Be concise, friendly, and practical. When you give advice, base it on the forecast data provided when available. If no data is provided, say so and give general tips. Do not make up specific numbers or dates; only use the data you are given.`
  if (!weekContext?.days?.length) {
    return `${base}\n\nNo week forecast data was provided. Suggest the user check their location or try again to load the forecast, and offer general allergy/asthma tips for the week.`
  }
  const lines = [
    base,
    "",
    "Forecast data for the next 7 days (use this to answer questions about specific days, pollen, air quality, and risk):",
    "",
  ]
  for (const day of weekContext.days) {
    const d = day.daily
    const risk = day.risk
    const factors = (day.activeRiskFactors ?? [])
      .map((f) => f.label)
      .filter(Boolean)
    lines.push(
      `- ${day.date} (${d?.day_of_week ?? "—"}): Risk ${risk?.label ?? "—"} (score ${risk?.score ?? "—"}). ` +
        `Factors: ${factors.length ? factors.join(", ") : "—"}. ` +
        `AQI: ${d?.AQI ?? "—"}, PM2.5 mean: ${d?.PM2_5_mean ?? "—"}, temp: ${d?.temp_min ?? "—"}–${d?.temp_max ?? "—"} °C, humidity: ${d?.humidity ?? "—"}%. ` +
        `Pollen: tree ${d?.pollen_tree ?? "—"}, grass ${d?.pollen_grass ?? "—"}, weed ${d?.pollen_weed ?? "—"}.`
    )
  }
  lines.push(
    "",
    "When users ask about 'this week' or 'future days', refer to the dates and values above. Suggest practical steps: limiting outdoor time on high-risk days, using medication as prescribed, checking air quality before exercise, and keeping windows closed when pollen or AQI is high."
  )
  return lines.join("\n")
}

export async function POST(request: Request) {
  const key = process.env.GEMINI_KEY ?? process.env.GEMINI_API_KEY
  if (!key?.trim()) {
    return NextResponse.json(
      { error: "Gemini API key not configured (GEMINI_KEY or GEMINI_API_KEY)." },
      { status: 500 }
    )
  }

  let body: {
    messages?: Array<{ role: string; content: string }>
    weekContext?: { start?: string; days: WeekDayContext[] }
  }
  try {
    body = await request.json()
  } catch {
    return NextResponse.json(
      { error: "Invalid JSON body." },
      { status: 400 }
    )
  }

  const messages = body.messages ?? []
  const weekContext = body.weekContext ?? null

  const contents: Array<{ role: string; parts: Array<{ text: string }> }> = []
  for (const m of messages) {
    const role = m.role === "model" || m.role === "assistant" ? "model" : "user"
    const text = typeof m.content === "string" ? m.content.trim() : ""
    if (!text) continue
    contents.push({ role, parts: [{ text }] })
  }

  if (contents.length === 0) {
    return NextResponse.json(
      { error: "At least one message is required." },
      { status: 400 }
    )
  }

  const systemInstruction = buildSystemInstruction(weekContext)
  const payload = {
    system_instruction: { parts: [{ text: systemInstruction }] },
    contents,
    generationConfig: {
      temperature: 0.7,
      maxOutputTokens: 1024,
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
  } catch (err) {
    console.error("[api/chat] Gemini request failed:", err)
    return NextResponse.json(
      { error: "Failed to reach the assistant. Please try again." },
      { status: 502 }
    )
  }

  const data = await res.json().catch(() => ({}))
  if (!res.ok) {
    const message =
      data?.error?.message || data?.error?.status || res.statusText
    console.error("[api/chat] Gemini error:", res.status, message)
    return NextResponse.json(
      { error: "The assistant could not respond. Please try again." },
      { status: res.status >= 500 ? 502 : 400 }
    )
  }

  const text =
    data?.candidates?.[0]?.content?.parts?.[0]?.text ??
    data?.candidates?.[0]?.content?.parts?.[0]?.text?.trim?.()
  if (typeof text !== "string") {
    return NextResponse.json(
      { error: "No reply from the assistant." },
      { status: 502 }
    )
  }

  return NextResponse.json({ reply: text })
}

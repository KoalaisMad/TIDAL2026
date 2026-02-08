import { NextResponse } from "next/server"
import { getUsersForHighRiskAlerts } from "@/lib/users"
import { sendHighRiskAlert } from "@/lib/email"

function toLocalDateStr(d: Date): string {
  const y = d.getFullYear()
  const m = String(d.getMonth() + 1).padStart(2, "0")
  const day = String(d.getDate()).padStart(2, "0")
  return `${y}-${m}-${day}`
}

/**
 * GET /api/cron/daily-high-risk
 * Call once per day (e.g. evening) to email users when tomorrow has high asthma risk.
 * Secured by CRON_SECRET: pass ?secret=CRON_SECRET or Authorization: Bearer CRON_SECRET.
 */
export async function GET(request: Request) {
  const url = new URL(request.url)
  const secretParam = url.searchParams.get("secret")
  const authHeader = request.headers.get("authorization")
  const bearerSecret = authHeader?.startsWith("Bearer ") ? authHeader.slice(7) : null
  const cronSecret = process.env.CRON_SECRET

  if (!cronSecret || (secretParam !== cronSecret && bearerSecret !== cronSecret)) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 })
  }

  const baseUrl = (process.env.NEXTAUTH_URL || "").replace(/\/$/, "")
  if (!baseUrl) {
    return NextResponse.json(
      { error: "NEXTAUTH_URL not set; cannot call week API" },
      { status: 500 }
    )
  }

  const today = new Date()
  const tomorrow = new Date(today)
  tomorrow.setDate(tomorrow.getDate() + 1)
  const tomorrowStr = toLocalDateStr(tomorrow)

  let users: Array<{ email: string; name?: string; location: string }>
  try {
    users = await getUsersForHighRiskAlerts()
  } catch (err) {
    console.error("daily-high-risk: getUsersForHighRiskAlerts error:", err)
    return NextResponse.json({ error: "Failed to load users" }, { status: 500 })
  }

  const results: Array<{ email: string; sent: boolean; error?: string }> = []

  for (const user of users) {
    let riskLevel: string | null = null
    let riskLabel: string | null = null

    try {
      const weekUrl = `${baseUrl}/api/week?start=${encodeURIComponent(tomorrowStr)}&days=1&location=${encodeURIComponent(user.location)}`
      const res = await fetch(weekUrl, { cache: "no-store" })
      if (!res.ok) {
        results.push({ email: user.email, sent: false, error: `week API ${res.status}` })
        continue
      }
      const data = await res.json()
      const firstDay = data?.days?.[0]
      if (firstDay?.risk) {
        riskLevel = firstDay.risk.level
        riskLabel = firstDay.risk.label ?? firstDay.risk.level
      }
    } catch (err) {
      results.push({
        email: user.email,
        sent: false,
        error: err instanceof Error ? err.message : "week fetch failed",
      })
      continue
    }

    if (riskLevel !== "high") {
      results.push({ email: user.email, sent: false })
      continue
    }

    const sendResult = await sendHighRiskAlert(user.email, {
      name: user.name,
      date: tomorrowStr,
      riskLabel: riskLabel ?? "High",
    })
    results.push({
      email: user.email,
      sent: sendResult.ok,
      error: sendResult.error,
    })
  }

  return NextResponse.json({
    date: tomorrowStr,
    usersChecked: users.length,
    results,
  })
}

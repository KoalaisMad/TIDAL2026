import { NextResponse } from "next/server"
import { getAllUsersWithEmail } from "@/lib/users"
import { sendDailyMorningNotification } from "@/lib/email"

function toLocalDateStr(d: Date): string {
  const y = d.getFullYear()
  const m = String(d.getMonth() + 1).padStart(2, "0")
  const day = String(d.getDate()).padStart(2, "0")
  return `${y}-${m}-${day}`
}

/**
 * GET /api/cron/daily-morning-notification
 * Intended to run daily at 8:00 AM (schedule via Vercel Cron, cron-job.org, or similar).
 * Sends a morning email to all users with a link to the Wheeze-Wise dashboard.
 * Secured by CRON_SECRET: pass ?secret=CRON_SECRET or Authorization: Bearer CRON_SECRET.
 */
export async function GET(request: Request) {
  const url = new URL(request.url)
  const secretParam = url.searchParams.get("secret")
  const authHeader = request.headers.get("authorization")
  const bearerSecret = authHeader?.startsWith("Bearer ")
    ? authHeader.slice(7)
    : null
  const cronSecret = process.env.CRON_SECRET

  if (
    !cronSecret ||
    (secretParam !== cronSecret && bearerSecret !== cronSecret)
  ) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 })
  }

  const todayStr = toLocalDateStr(new Date())

  let users: Array<{ email: string; name?: string }>
  try {
    users = await getAllUsersWithEmail()
  } catch (err) {
    console.error("daily-morning-notification: getAllUsersWithEmail error:", err)
    return NextResponse.json(
      { error: "Failed to load users" },
      { status: 500 }
    )
  }

  const results: Array<{ email: string; sent: boolean; error?: string }> = []

  for (const user of users) {
    if (!user.email?.trim()) {
      results.push({ email: user.email ?? "", sent: false, error: "No email" })
      continue
    }
    const sendResult = await sendDailyMorningNotification(user.email, {
      name: user.name,
      date: todayStr,
    })
    results.push({
      email: user.email,
      sent: sendResult.ok,
      error: sendResult.error,
    })
  }

  return NextResponse.json({
    date: todayStr,
    usersNotified: users.length,
    results,
  })
}

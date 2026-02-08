import { NextResponse } from "next/server"
import { getServerSession } from "next-auth/next"
import { authOptions } from "@/app/api/auth/[...nextauth]/route"
import { getUserByEmail } from "@/lib/users"
import { sendHighRiskAlert } from "@/lib/email"

function toLocalDateStr(d: Date): string {
  const y = d.getFullYear()
  const m = String(d.getMonth() + 1).padStart(2, "0")
  const day = String(d.getDate()).padStart(2, "0")
  return `${y}-${m}-${day}`
}

/**
 * POST /api/cron/daily-high-risk/test
 * Sends a test high-risk alert email to the current user (for testing).
 * Requires authentication.
 */
export async function POST() {
  const session = await getServerSession(authOptions)
  if (!session?.user?.email) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 })
  }

  const user = await getUserByEmail(session.user.email)
  const tomorrow = new Date()
  tomorrow.setDate(tomorrow.getDate() + 1)
  const tomorrowStr = toLocalDateStr(tomorrow)

  const sendResult = await sendHighRiskAlert(session.user.email, {
    name: user?.name ?? session.user.name ?? undefined,
    date: tomorrowStr,
    riskLabel: "High (test)",
  })

  if (!sendResult.ok) {
    return NextResponse.json(
      { ok: false, error: sendResult.error ?? "Failed to send" },
      { status: 500 }
    )
  }

  return NextResponse.json({
    ok: true,
    message: "Test high-risk email sent",
    to: session.user.email,
    date: tomorrowStr,
  })
}

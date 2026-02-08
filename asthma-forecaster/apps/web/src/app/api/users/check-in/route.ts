import { NextResponse } from "next/server"
import { getServerSession } from "next-auth/next"
import { authOptions } from "@/app/api/auth/[...nextauth]/route"
import { addCheckIn } from "@/lib/users"

export async function POST(request: Request) {
  const session = await getServerSession(authOptions)
  if (!session?.user?.email) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 })
  }

  let body: {
    date?: string
    wheeze?: number
    cough?: number
    chestTightness?: number
    exerciseMinutes?: number
  }
  try {
    body = await request.json()
  } catch {
    return NextResponse.json({ error: "Invalid JSON" }, { status: 400 })
  }

  // Store daily check-in in DB: wheeze (0–3), cough (0–3), chestTightness (0–3), exerciseMinutes
  const date =
    body.date ??
    new Date().toISOString().slice(0, 10)
  const wheeze = Math.min(3, Math.max(0, typeof body.wheeze === "number" ? body.wheeze : 0))
  const cough = Math.min(3, Math.max(0, typeof body.cough === "number" ? body.cough : 0))
  const chestTightness = Math.min(
    3,
    Math.max(0, typeof body.chestTightness === "number" ? body.chestTightness : 0)
  )
  const exerciseMinutes = Math.min(
    1440,
    Math.max(0, typeof body.exerciseMinutes === "number" ? body.exerciseMinutes : 0)
  )

  try {
    await addCheckIn(session.user.email, {
      date,
      wheeze,
      cough,
      chestTightness,
      exerciseMinutes,
    })
    return NextResponse.json({ ok: true })
  } catch (err) {
    console.error("POST /api/users/check-in DB error:", err)
    return NextResponse.json(
      { error: "Database unavailable" },
      { status: 503 }
    )
  }
}

import { NextResponse } from "next/server"
import { getServerSession } from "next-auth/next"
import { authOptions } from "@/app/api/auth/[...nextauth]/route"
import { createOrUpdateUser, getUserByEmail } from "@/lib/users"

export async function GET() {
  const session = await getServerSession(authOptions)
  if (!session?.user?.email) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 })
  }

  try {
    const user = await getUserByEmail(session.user.email)
    if (!user) {
      return NextResponse.json({ registered: false }, { status: 200 })
    }
    return NextResponse.json({
      registered: true,
      email: user.email,
      name: user.name,
      location: user.location,
      profile: user.profile, // height, weight, gender, smokerStatus, petExposure, bmi
      checkIns: user.checkIns ?? [], // daily check-ins: wheeze, cough, chestTightness, exerciseMinutes
    })
  } catch (err) {
    console.error("GET /api/users/me DB error:", err)
    return NextResponse.json(
      { error: "Database unavailable", registered: false },
      { status: 503 }
    )
  }
}

/** PATCH /api/users/me — update current user (e.g. location for high-risk alerts). */
export async function PATCH(request: Request) {
  const session = await getServerSession(authOptions)
  if (!session?.user?.email) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 })
  }

  let body: { location?: string }
  try {
    body = await request.json()
  } catch {
    return NextResponse.json({ error: "Invalid JSON" }, { status: 400 })
  }

  try {
    const updates: { location?: string } = {}
    if (body.location !== undefined) updates.location = body.location?.trim() || undefined
    if (Object.keys(updates).length === 0) {
      return NextResponse.json({ ok: true })
    }
    await createOrUpdateUser(session.user.email, updates)
    return NextResponse.json({ ok: true })
  } catch (err) {
    console.error("PATCH /api/users/me DB error:", err)
    return NextResponse.json(
      { error: "Database unavailable" },
      { status: 503 }
    )
  }
}

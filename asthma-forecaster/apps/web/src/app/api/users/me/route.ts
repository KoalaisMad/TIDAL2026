import { NextResponse } from "next/server"
import { getServerSession } from "next-auth/next"
import { authOptions } from "@/app/api/auth/[...nextauth]/route"
import { getUserByEmail } from "@/lib/users"

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

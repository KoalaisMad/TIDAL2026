import { NextResponse } from "next/server"
import { getServerSession } from "next-auth/next"
import { authOptions } from "@/app/api/auth/[...nextauth]/route"
import { createOrUpdateUser, getUserByEmail } from "@/lib/users"
import type { UserProfile } from "@/lib/users"

export async function POST(request: Request) {
  const session = await getServerSession(authOptions)
  if (!session?.user?.email) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 })
  }

  let body: {
    name?: string
    height?: string
    weight?: string
    gender?: string
    smokerStatus?: string
    petExposure?: string
    bmi?: number
  }
  try {
    body = await request.json()
  } catch {
    return NextResponse.json({ error: "Invalid JSON" }, { status: 400 })
  }

  try {
    // Persist full profile in DB: name, height, weight (for BMI), gender, smokerStatus, petExposure, bmi
    const incoming: UserProfile = {}
    if (body.name !== undefined) incoming.name = body.name
    if (body.height !== undefined) incoming.height = body.height
    if (body.weight !== undefined) incoming.weight = body.weight
    if (body.gender !== undefined) incoming.gender = body.gender
    if (body.smokerStatus !== undefined) incoming.smokerStatus = body.smokerStatus
    if (body.petExposure !== undefined) incoming.petExposure = body.petExposure
    if (body.bmi !== undefined) incoming.bmi = body.bmi

    const existing = await getUserByEmail(session.user.email)
    const hasIncoming = Object.keys(incoming).length > 0
    const merged = hasIncoming ? { ...existing?.profile, ...incoming } : existing?.profile

    // Always write the full profile shape so DB has all keys (height, weight, gender, smokerStatus, petExposure, bmi)
    const PROFILE_KEYS: (keyof UserProfile)[] = [
      "name",
      "height",
      "weight",
      "gender",
      "smokerStatus",
      "petExposure",
      "bmi",
    ]
    const fullProfile: UserProfile = {}
    for (const key of PROFILE_KEYS) {
      const v = merged?.[key]
      fullProfile[key] = v === undefined ? null : (v as UserProfile[keyof UserProfile])
    }

    await createOrUpdateUser(session.user.email, {
      name: body.name ?? session.user.name ?? existing?.name ?? undefined,
      profile: hasIncoming ? fullProfile : undefined,
    })
    return NextResponse.json({ ok: true })
  } catch (err) {
    console.error("POST /api/users/register DB error:", err)
    return NextResponse.json(
      { error: "Database unavailable" },
      { status: 503 }
    )
  }
}

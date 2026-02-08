import { NextResponse } from "next/server"
import { getServerSession } from "next-auth/next"
import { authOptions } from "@/app/api/auth/[...nextauth]/route"
import { createOrUpdateUser } from "@/lib/users"

export async function POST(request: Request) {
  const session = await getServerSession(authOptions)
  if (!session?.user?.email) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 })
  }

  let body: { name?: string; height?: string; weight?: string; gender?: string }
  try {
    body = await request.json()
  } catch {
    return NextResponse.json({ error: "Invalid JSON" }, { status: 400 })
  }

  try {
    await createOrUpdateUser(session.user.email, {
      name: body.name ?? session.user.name ?? undefined,
      profile: {
        name: body.name,
        height: body.height,
        weight: body.weight,
        gender: body.gender,
      },
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

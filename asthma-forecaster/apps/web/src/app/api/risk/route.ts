import { NextResponse } from "next/server"

import { DUMMY_ACTIVE_RISK_FACTORS, isIsoDate } from "../_mock"

export function GET(request: Request) {
  const url = new URL(request.url)
  const date = url.searchParams.get("date")

  if (!isIsoDate(date)) {
    return NextResponse.json(
      { error: "Missing or invalid `date` (expected YYYY-MM-DD)." },
      { status: 400 }
    )
  }

  // Stubbed to mirror current UI dummy values.
  const score = 3
  const level = "moderate" as const
  const label = "Moderate"

  return NextResponse.json({
    date,
    risk: { score, level, label },
    activeRiskFactors: DUMMY_ACTIVE_RISK_FACTORS,
  })
}


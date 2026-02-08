import { NextResponse } from "next/server"

import { DUMMY_RECOMMENDATIONS, isIsoDate, isRiskLevel } from "../_mock"

export function GET(request: Request) {
  const url = new URL(request.url)
  const date = url.searchParams.get("date")
  const riskLevel = url.searchParams.get("riskLevel")

  if (!isIsoDate(date)) {
    return NextResponse.json(
      { error: "Missing or invalid `date` (expected YYYY-MM-DD)." },
      { status: 400 }
    )
  }

  if (!isRiskLevel(riskLevel)) {
    return NextResponse.json(
      {
        error:
          "Missing or invalid `riskLevel` (expected one of: low, moderate, high).",
      },
      { status: 400 }
    )
  }

  // Stub: for now, return the same dummy set regardless of date/level.
  // (Keeping the signature in place so you can swap in real logic later.)
  return NextResponse.json({
    date,
    riskLevel,
    recommendations: DUMMY_RECOMMENDATIONS,
  })
}


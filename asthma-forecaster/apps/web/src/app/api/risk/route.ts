import { NextResponse } from "next/server"
import fs from "fs"
import path from "path"
import { spawnSync } from "child_process"

import { DUMMY_ACTIVE_RISK_FACTORS, isIsoDate } from "../_mock"

/** Root of TIDAL2026 (where risk_model_general.joblib and .env live). Set TIDAL_ROOT if needed. */
function getTidalRoot(): string {
  const env = process.env.TIDAL_ROOT
  if (env) return path.resolve(env)
  const cwd = process.cwd()
  const candidates = [
    cwd,
    path.resolve(cwd, ".."),
    path.resolve(cwd, "..", ".."),
    path.resolve(cwd, "..", "..", ".."),
  ]
  for (const dir of candidates) {
    if (
      fs.existsSync(path.join(dir, "risk_model_general.joblib")) ||
      fs.existsSync(path.join(dir, "asthma-forecaster", "apps", "ml", "predict_risk.py"))
    ) {
      return dir
    }
  }
  return path.resolve(cwd, "..", "..", "..")
}

export async function GET(request: Request) {
  const url = new URL(request.url)
  const date = url.searchParams.get("date")

  if (!isIsoDate(date)) {
    return NextResponse.json(
      { error: "Missing or invalid `date` (expected YYYY-MM-DD)." },
      { status: 400 }
    )
  }

  const tidalRoot = getTidalRoot()
  const result = spawnSync(
    "python3",
    ["-m", "apps.ml.predict_risk", "--date", date!],
    {
      cwd: tidalRoot,
      encoding: "utf-8",
      env: { ...process.env, PYTHONPATH: path.join(tidalRoot, "asthma-forecaster") },
      timeout: 15000,
    }
  )

  if (result.status === 0 && result.stdout) {
    try {
      const data = JSON.parse(result.stdout.trim()) as {
        error?: string
        date: string
        risk: { score: number; level: string; label: string }
        activeRiskFactors: Array<{ id: string; label: string; iconKey: string }>
      }
      if (data.risk) {
        return NextResponse.json({
          date: data.date,
          risk: data.risk,
          activeRiskFactors:
            data.activeRiskFactors?.length > 0
              ? data.activeRiskFactors
              : DUMMY_ACTIVE_RISK_FACTORS,
        })
      }
    } catch {
      // fall through to stub
    }
  }

  // Stub fallback: same shape as preexisting endpoint (no frontend change)
  return NextResponse.json({
    date,
    risk: { score: 3, level: "moderate", label: "Moderate" },
    activeRiskFactors: DUMMY_ACTIVE_RISK_FACTORS,
  })
}

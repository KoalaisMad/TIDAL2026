import { NextResponse } from "next/server"
import fs from "fs"
import path from "path"
import { spawnSync } from "child_process"

import { isIsoDate } from "../_mock"

function toFloatScore(n: number): number {
  return Math.round(Number(n) * 10) / 10
}

function getTidalRoot(): string {
  const env = process.env.TIDAL_ROOT
  if (env) return path.resolve(env)
  const cwd = process.cwd()
  const candidates = [
    cwd,
    path.resolve(cwd, ".."),
    path.resolve(cwd, "..", ".."),
    path.resolve(cwd, "..", "..", ".."),
    path.resolve(cwd, "..", "..", "..", ".."),
    path.join(cwd, "TIDAL2026"),
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

function loadTidalEnv(tidalRoot: string): void {
  const envPath = path.join(tidalRoot, ".env")
  if (!fs.existsSync(envPath)) return
  try {
    const content = fs.readFileSync(envPath, "utf-8")
    for (const line of content.split("\n")) {
      const m = line.match(/^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)$/)
      if (m) {
        const key = m[1]
        let val = m[2].trim()
        if ((val.startsWith('"') && val.endsWith('"')) || (val.startsWith("'") && val.endsWith("'")))
          val = val.slice(1, -1)
        if (!process.env[key]) process.env[key] = val
      }
    }
  } catch {
    // ignore
  }
}

function toLocalDateStr(d: Date): string {
  const y = d.getFullYear()
  const m = String(d.getMonth() + 1).padStart(2, "0")
  const day = String(d.getDate()).padStart(2, "0")
  return `${y}-${m}-${day}`
}

function toLocationId(location: string | null): string | null {
  if (!location?.trim()) return null
  const s = location.trim()
  const latLon = /^(-?\d+\.?\d*),(-?\d+\.?\d*)$/.exec(s)
  if (latLon) {
    const lat = Math.round(parseFloat(latLon[1]) * 10000) / 10000
    const lon = Math.round(parseFloat(latLon[2]) * 10000) / 10000
    return `${lat}_${lon}`
  }
  if (/^\d{5}(-\d{4})?$/.test(s)) return `zip_${s.replace(/-.*/, "")}`
  return s
}

/** GET /api/week?start=YYYY-MM-DD&days=7&location=... — next N days using environment risk model (trainingModel / predict_risk). */
export async function GET(request: Request) {
  const url = new URL(request.url)
  let start = url.searchParams.get("start")
  if (!start || !isIsoDate(start)) {
    start = toLocalDateStr(new Date())
  }
  const daysParam = url.searchParams.get("days")
  const days = Math.min(14, Math.max(1, daysParam ? parseInt(daysParam, 10) : 7)) || 7
  const locationId = toLocationId(url.searchParams.get("location") ?? url.searchParams.get("location_id"))

  const tidalRoot = getTidalRoot()
  loadTidalEnv(tidalRoot)

  // Environment risk uses trainingModel pipeline (predict_risk loads risk_model_general.joblib)
  const py = process.platform === "win32" ? "python" : "python3"
  const args = ["-m", "apps.ml.predict_risk", "--week", "--start", start, "--days", String(days)]
  if (locationId) args.push("--location-id", locationId)

  let result = spawnSync(py, args, {
    cwd: tidalRoot,
    encoding: "utf-8",
    env: { ...process.env, PYTHONPATH: path.join(tidalRoot, "asthma-forecaster") },
    timeout: 30000,
  })
  const errCode = (result.error as NodeJS.ErrnoException)?.code
  if (result.status !== 0 && errCode === "ENOENT" && process.platform !== "win32") {
    result = spawnSync("python", args, {
      cwd: tidalRoot,
      encoding: "utf-8",
      env: { ...process.env, PYTHONPATH: path.join(tidalRoot, "asthma-forecaster") },
      timeout: 30000,
    })
  }

  const stdout = typeof result.stdout === "string" ? result.stdout.trim() : ""
  if (result.status === 0 && stdout) {
    try {
      const data = JSON.parse(stdout) as {
        start: string
        days: Array<{
          date: string
          risk: { score: number; level: string; label: string }
          activeRiskFactors: Array<{ id: string; label: string; iconKey: string }>
          daily?: Record<string, unknown>
        }>
      }
      if (Array.isArray(data.days)) {
        const days = data.days.map((d: { date: string; risk: { score: number; level: string; label: string }; activeRiskFactors?: unknown[]; daily?: unknown }) => ({
          ...d,
          risk: {
            ...d.risk,
            score: toFloatScore(d.risk.score),
          },
        }))
        return NextResponse.json({ start: data.start, days: days })
      }
    } catch {
      // fall through
    }
  }

  const fallbackStart = start ?? toLocalDateStr(new Date())
  const fallbackDays = []
  const levels: Array<{ score: number; level: string; label: string }> = [
    { score: 1.5, level: "low", label: "Low" },
    { score: 2.0, level: "low", label: "Low" },
    { score: 2.5, level: "moderate", label: "Moderate" },
    { score: 3.0, level: "moderate", label: "Moderate" },
    { score: 3.5, level: "moderate", label: "Moderate" },
    { score: 4.0, level: "high", label: "High" },
    { score: 4.5, level: "high", label: "High" },
  ]
  for (let i = 0; i < days; i++) {
    const d = new Date(fallbackStart + "T12:00:00")
    d.setDate(d.getDate() + i)
    const risk = levels[i % levels.length]
    fallbackDays.push({
      date: toLocalDateStr(d),
      risk: { score: toFloatScore(risk.score), level: risk.level, label: risk.label },
      activeRiskFactors: [],
      daily: {},
    })
  }
  return NextResponse.json({ start: fallbackStart, days: fallbackDays })
}

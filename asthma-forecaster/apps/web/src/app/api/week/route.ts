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
      fs.existsSync(path.join(dir, "asthma-forecaster", "apps", "ml", "predict_risk.py")) ||
      fs.existsSync(path.join(dir, "asthma-forecaster", "apps", "ml", "predict_flare.py")) ||
      fs.existsSync(path.join(dir, "asthma-forecaster", "apps", "D A T A", "flare_model.joblib"))
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

/** GET /api/week?start=YYYY-MM-DD&days=7&location=... — next N days using flare model (predict_flare). */
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

  const envWithPath = {
    ...process.env,
    PYTHONPATH: path.join(tidalRoot, "asthma-forecaster"),
    TIDAL_ROOT: tidalRoot,
  }

  const args = ["-m", "apps.ml.predict_flare", "--week", "--start", start, "--days", String(days)]
  if (locationId) args.push("--location-id", locationId)
  // Pass --lat/--lon when location is "lat_lon" so flare script can fetch week data via API
  if (locationId && !locationId.startsWith("zip_") && locationId.includes("_")) {
    const parts = locationId.split("_", 2)
    const lat = parseFloat(parts[0])
    const lon = parseFloat(parts[1])
    if (Number.isFinite(lat) && Number.isFinite(lon)) {
      args.push("--lat", String(lat), "--lon", String(lon))
    }
  }

  // Prefer venv Python (same one used by apps/ml/run.ps1) so model runs even when system py/python is broken
  const venvPy =
    process.platform === "win32"
      ? path.join(tidalRoot, "asthma-forecaster", "apps", "ml", ".venv", "Scripts", "python.exe")
      : path.join(tidalRoot, "asthma-forecaster", "apps", "ml", ".venv", "bin", "python")
  const pyCandidates: string[] =
    fs.existsSync(venvPy) ? [venvPy] : process.platform === "win32" ? ["py", "python"] : ["python3", "python"]

  let result: ReturnType<typeof spawnSync> = { status: -1, stdout: "", stderr: "", output: [], signal: null, error: undefined }
  for (const py of pyCandidates) {
    result = spawnSync(py, args, {
      cwd: tidalRoot,
      encoding: "utf-8",
      env: envWithPath,
      timeout: 30000,
    })
    if (result.status === 0 && typeof result.stdout === "string" && result.stdout.trim()) break
    if (result.error && (result.error as NodeJS.ErrnoException).code === "ENOENT") continue
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
        const mappedDays = data.days.map((d: { date: string; risk: { score: number; level: string; label: string }; activeRiskFactors?: unknown[]; daily?: unknown }) => ({
          ...d,
          risk: {
            ...d.risk,
            score: toFloatScore(d.risk.score),
          },
        }))
        return NextResponse.json({ start: data.start, days: mappedDays, fromModel: true })
      }
    } catch {
      // fall through
    }
  }

  // Log why the model didn't run so you can fix env/Python/model path
  if (result.status !== 0 || !stdout) {
    const stderr = typeof result.stderr === "string" ? result.stderr.trim() : ""
    const err = result.error as NodeJS.ErrnoException | undefined
    console.error(
      "[api/week] Model fallback: status=%s stderr=%s error=%s",
      result.status,
      stderr || "(none)",
      err?.message ?? err?.code ?? "(none)"
    )
  }

  const fallbackStart = start ?? toLocalDateStr(new Date())
  const WEEKDAY_NAMES = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]
  const SEASONS = ["winter", "spring", "summer", "fall"]
  const fallbackDays: Array<{
    date: string
    risk: { score: number; level: string; label: string }
    activeRiskFactors: unknown[]
    daily: Record<string, unknown>
  }> = []
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
    const dateStr = toLocalDateStr(d)
    const risk = levels[i % levels.length]
    const month = d.getMonth() + 1
    const seasonIdx = Math.floor(((month % 12) + 3) / 3) - 1
    const season = SEASONS[seasonIdx] ?? "—"
    fallbackDays.push({
      date: dateStr,
      risk: { score: toFloatScore(risk.score), level: risk.level, label: risk.label },
      activeRiskFactors: [],
      daily: {
        date: dateStr,
        day_of_week: WEEKDAY_NAMES[d.getDay()],
        season,
        AQI: null,
        PM2_5_mean: null,
        PM2_5_max: null,
        temp_min: null,
        temp_max: null,
        humidity: null,
        pollen_tree: null,
        pollen_grass: null,
        pollen_weed: null,
      },
    })
  }
  return NextResponse.json({ start: fallbackStart, days: fallbackDays, fromModel: false })
}

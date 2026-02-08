import { NextResponse } from "next/server"
import fs from "fs"
import path from "path"
import { spawnSync } from "child_process"

import { DUMMY_ACTIVE_RISK_FACTORS, isIsoDate } from "../_mock"

function toFloatScore(n: number): number {
  return Math.round(Number(n) * 10) / 10
}

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
    path.resolve(cwd, "..", "..", "..", ".."),
    path.join(cwd, "TIDAL2026"),
    path.resolve(cwd, "..", "..", "..", "TIDAL2026"),
    path.resolve(cwd, "..", "..", "TIDAL2026"),
  ]
  const hasTidal = (dir: string) =>
    fs.existsSync(path.join(dir, "risk_model_general.joblib")) ||
    fs.existsSync(path.join(dir, "asthma-forecaster", "apps", "ml", "predict_risk.py")) ||
    fs.existsSync(path.join(dir, "asthma-forecaster", "apps", "ml", "predict_flare.py")) ||
    fs.existsSync(path.join(dir, "asthma-forecaster", "apps", "D A T A", "flare_model.joblib"))
  for (const dir of candidates) {
    if (hasTidal(dir)) return dir
    const tidal2026 = path.join(dir, "TIDAL2026")
    if (fs.existsSync(tidal2026) && hasTidal(tidal2026)) return tidal2026
  }
  return path.resolve(cwd, "..", "..", "..")
}

/** Load .env from TIDAL root and web cwd so spawned Python gets MONGODB_URI etc. */
function loadTidalEnv(tidalRoot: string): void {
  const loadFrom = (envPath: string) => {
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
  loadFrom(path.join(tidalRoot, ".env"))
  loadFrom(path.join(process.cwd(), ".env"))
  loadFrom(path.join(process.cwd(), ".env.local"))
}

function getPythonCandidates(tidalRoot: string): string[] {
  const venvPy =
    process.platform === "win32"
      ? path.join(tidalRoot, "asthma-forecaster", "apps", "ml", ".venv", "Scripts", "python.exe")
      : path.join(tidalRoot, "asthma-forecaster", "apps", "ml", ".venv", "bin", "python")
  if (fs.existsSync(venvPy)) return [venvPy]
  return process.platform === "win32" ? ["py", "python"] : ["python3", "python"]
}

function runPython(
  tidalRoot: string,
  date: string,
  pythonCmd?: string,
  locationId?: string | null
): ReturnType<typeof spawnSync> {
  const candidates = pythonCmd ? [pythonCmd] : getPythonCandidates(tidalRoot)
  const args = ["-m", "apps.ml.predict_flare", "--date", date]
  if (locationId?.trim()) args.push("--location-id", locationId.trim())
  const env = { ...process.env, PYTHONPATH: path.join(tidalRoot, "asthma-forecaster"), TIDAL_ROOT: tidalRoot }
  for (const py of candidates) {
    const result = spawnSync(py, args, {
      cwd: tidalRoot,
      encoding: "utf-8",
      env,
      timeout: 15000,
    })
    if (result.status === 0 && typeof result.stdout === "string" && result.stdout.trim()) return result
    if (result.error && (result.error as NodeJS.ErrnoException).code === "ENOENT") continue
    return result
  }
  return spawnSync(candidates[0], args, { cwd: tidalRoot, encoding: "utf-8", env, timeout: 15000 })
}

/** Normalize user location to location_id: "lat,lon" -> "lat_lon", ZIP -> zip_XXXXX. */
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

export async function GET(request: Request) {
  const url = new URL(request.url)
  const date = url.searchParams.get("date")
  const locationId = toLocationId(url.searchParams.get("location") ?? url.searchParams.get("location_id"))

  if (!isIsoDate(date)) {
    return NextResponse.json(
      { error: "Missing or invalid `date` (expected YYYY-MM-DD)." },
      { status: 400 }
    )
  }

  const tidalRoot = getTidalRoot()
  loadTidalEnv(tidalRoot)

  // Flare model (predict_flare loads D A T A/flare_model.joblib)
  const result = runPython(tidalRoot, date!, undefined, locationId)
  const stdout = typeof result.stdout === "string" ? result.stdout.trim() : ""
  if (stdout) {
    try {
      const data = JSON.parse(stdout) as {
        error?: string
        date: string
        risk?: { score: number; level: string; label: string }
        activeRiskFactors?: Array<{ id: string; label: string; iconKey: string }>
        daily?: Record<string, unknown>
      }
      if (data.risk) {
        const body: Record<string, unknown> = {
          date: data.date,
          risk: {
            ...data.risk,
            score: toFloatScore(data.risk.score),
          },
          activeRiskFactors:
            (data.activeRiskFactors?.length ?? 0) > 0
              ? data.activeRiskFactors!
              : DUMMY_ACTIVE_RISK_FACTORS,
        }
        if (data.daily != null) body.daily = data.daily
        return NextResponse.json(body)
      }
    } catch {
      // fall through
    }
  }
  const stderr = typeof result.stderr === "string" ? result.stderr.trim() : ""
  const err = result.error as NodeJS.ErrnoException | undefined
  console.error(
    "[api/risk] Model fallback: status=%s stderr=%s error=%s",
    result.status,
    stderr || "(none)",
    err?.message ?? err?.code ?? "(none)"
  )
  const fallbackByDate = (d: string) => {
    const n = d.split("").reduce((acc, c) => acc + c.charCodeAt(0), 0)
    const score = 1.5 + (n % 30) / 10
    const clamped = Math.min(5, Math.max(1, score))
    const level = clamped < 2 ? "low" : clamped < 4 ? "moderate" : "high"
    const label = level === "low" ? "Low" : level === "moderate" ? "Moderate" : "High"
    return { score: Math.round(clamped * 10) / 10, level, label }
  }
  const risk = fallbackByDate(date!)
  return NextResponse.json({
    date,
    risk: { score: toFloatScore(risk.score), level: risk.level, label: risk.label },
    activeRiskFactors: DUMMY_ACTIVE_RISK_FACTORS,
  })
}

import { NextResponse } from "next/server"
import fs from "fs"
import path from "path"
import { spawnSync } from "child_process"

import { getServerSession } from "next-auth/next"
import { authOptions } from "@/app/api/auth/[...nextauth]/route"
import { getUserByEmail } from "@/lib/users"

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
  const hasScriptAndModel = (dir: string) => {
    const scriptPath = path.join(dir, "asthma-forecaster", "apps", "D A T A", "predict_personalized.py")
    const modelPath = path.join(dir, "asthma-forecaster", "apps", "D A T A", "flare_model.joblib")
    const personalizedModelPath = path.join(dir, "asthma-forecaster", "apps", "D A T A", "personalized_flare_model.joblib")
    const hasModel = fs.existsSync(personalizedModelPath) || fs.existsSync(modelPath)
    return fs.existsSync(scriptPath) && hasModel
  }
  for (const dir of candidates) {
    if (hasScriptAndModel(dir)) return dir
    const tidal2026 = path.join(dir, "TIDAL2026")
    if (fs.existsSync(tidal2026) && hasScriptAndModel(tidal2026)) return tidal2026
  }
  return path.resolve(cwd, "..", "..", "..")
}

/** Same Python discovery as risk route (venv first, then python3/python). */
function getPythonCandidates(tidalRoot: string): string[] {
  const venvPy =
    process.platform === "win32"
      ? path.join(tidalRoot, "asthma-forecaster", "apps", "ml", ".venv", "Scripts", "python.exe")
      : path.join(tidalRoot, "asthma-forecaster", "apps", "ml", ".venv", "bin", "python")
  if (fs.existsSync(venvPy)) return [venvPy]
  return process.platform === "win32" ? ["py", "python"] : ["python3", "python"]
}

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
  // Also load from web app cwd so MONGODB_URI from .env.local is available for the Python script
  loadFrom(path.join(process.cwd(), ".env"))
  loadFrom(path.join(process.cwd(), ".env.local"))
}

/** Ensure score is a float with two decimal places (e.g. 2.35, 3.70). */
function toFloatScore(n: number): number {
  return Math.round(Number(n) * 100) / 100
}

/** Map risk 1–5 (from probability-based predictions) to { score, level, label } */
function toRiskDisplay(value: number, targetCol: "risk" | "flare_day"): { score: number; level: string; label: string } {
  // Both risk and flare_day are now probability-based scores in 1-5 range
  // (flare_day probability mapped to 1-5, risk is weighted average of class probabilities)
  const raw = value <= 0 ? 1.5 : value
  const score = toFloatScore(Math.min(5, Math.max(1, raw)))
  const level = score <= 2 ? "low" : score <= 4 ? "moderate" : "high"
  const label = level === "low" ? "Low" : level === "moderate" ? "Moderate" : "High"
  return { score, level, label }
}

/** GET /api/risk/personalized — 7-day personalized predictions for the signed-in user (saved profile + check-ins). */
export async function GET() {
  const session = await getServerSession(authOptions)
  if (!session?.user?.email) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 })
  }

  const user = await getUserByEmail(session.user.email)
  if (!user?.email) {
    return NextResponse.json({ error: "User not found", days: [], fromModel: false }, { status: 200 })
  }

  const userId = user._id ?? null
  const tidalRoot = getTidalRoot()
  loadTidalEnv(tidalRoot)

  // Resolve script: prefer TIDAL root path; fallback to apps/D A T A when running from apps/web
  let scriptPath = path.join(tidalRoot, "asthma-forecaster", "apps", "D A T A", "predict_personalized.py")
  if (!fs.existsSync(scriptPath)) {
    scriptPath = path.resolve(process.cwd(), "..", "D A T A", "predict_personalized.py")
  }
  const scriptDir = path.dirname(scriptPath)
  const modelPath = path.join(scriptDir, "personalized_flare_model.joblib")
  const fallbackModelPath = path.join(scriptDir, "flare_model.joblib")
  const hasModel = fs.existsSync(modelPath) || fs.existsSync(fallbackModelPath)
  if (!fs.existsSync(scriptPath) || !hasModel) {
    if (process.env.NODE_ENV === "development") {
      console.error("[personalized risk] script or model not found:", { scriptPath, scriptDir, hasModel })
    }
    return fallbackDays()
  }

  const spawnEnv = {
    ...process.env,
    PYTHONPATH: path.join(tidalRoot, "asthma-forecaster"),
    TIDAL_ROOT: tidalRoot,
    MONGODB_DB_NAME: process.env.MONGODB_DB_NAME || "asthma",
    MONGODB_URI: process.env.MONGODB_URI || process.env.MONGO_URI || "",
  }
  const pyCandidates = getPythonCandidates(tidalRoot)
  let result = spawnSync(pyCandidates[0], [scriptPath, "--out", "-", "--days", "7"], {
    cwd: scriptDir,
    encoding: "utf-8",
    env: spawnEnv,
    timeout: 60000,
  })
  for (let i = 1; i < pyCandidates.length && (result.status !== 0 || !(typeof result.stdout === "string" && result.stdout.trim())); i++) {
    const err = result.error as NodeJS.ErrnoException | undefined
    if (err?.code === "ENOENT") {
      result = spawnSync(pyCandidates[i], [scriptPath, "--out", "-", "--days", "7"], {
        cwd: scriptDir,
        encoding: "utf-8",
        env: spawnEnv,
        timeout: 60000,
      })
    } else break
  }

  const stdout = typeof result.stdout === "string" ? result.stdout.trim() : ""
  const stderr = typeof result.stderr === "string" ? result.stderr.trim() : ""
  if (result.status !== 0 || !stdout) {
    if (process.env.NODE_ENV === "development" && stderr) {
      console.error("[personalized risk] predict_personalized.py failed:", stderr)
    }
    return fallbackDays(stderr)
  }

  let list: Array<{ user_id: string; date: string; risk?: number; flare_day?: number; probability?: number }>
  try {
    list = JSON.parse(stdout) as typeof list
  } catch {
    return fallbackDays()
  }

  const forUser = userId ? list.filter((p) => String(p.user_id) === String(userId)) : list
  if (forUser.length === 0) {
    if (process.env.NODE_ENV === "development") {
      console.warn("[personalized risk] script returned predictions but none for current user. userId:", userId, "list user_ids:", [...new Set(list.map((p) => p.user_id))])
    }
    return fallbackDays("No predictions for current user (user_id mismatch?)")
  }

  const hasRisk = forUser.some((p) => p.risk != null)
  const targetCol = hasRisk ? "risk" : "flare_day"

  const days = forUser
    .sort((a, b) => a.date.localeCompare(b.date))
    .slice(0, 7)
    .map((p) => {
      const value = (p.risk ?? p.flare_day ?? 1) as number
      const risk = toRiskDisplay(value, targetCol)
      const result: {
        date: string
        risk: { score: number; level: string; label: string; probability?: number }
        activeRiskFactors: Array<{ id: string; label: string; iconKey: string }>
      } = {
        date: p.date,
        risk: { score: toFloatScore(risk.score), level: risk.level, label: risk.label },
        activeRiskFactors: [] as Array<{ id: string; label: string; iconKey: string }>,
      }
      // Include probability if available (from predict_proba)
      if (p.probability != null) {
        result.risk.probability = toFloatScore(p.probability)
      }
      return result
    })

  const start = days[0]?.date ?? toLocalDateStr(new Date())
  return NextResponse.json({ start, days, fromModel: true })
}

/** Local YYYY-MM-DD so fallback dates match frontend strip (which uses local time). */
function toLocalDateStr(d: Date): string {
  const y = d.getFullYear()
  const m = String(d.getMonth() + 1).padStart(2, "0")
  const day = String(d.getDate()).padStart(2, "0")
  return `${y}-${m}-${day}`
}

function fallbackDays(debugStderr?: string): NextResponse {
  const now = new Date()
  const start = toLocalDateStr(now)
  const levels: Array<{ score: number; level: string; label: string }> = [
    { score: 1.5, level: "low", label: "Low" },
    { score: 2.0, level: "low", label: "Low" },
    { score: 2.5, level: "moderate", label: "Moderate" },
    { score: 3.0, level: "moderate", label: "Moderate" },
    { score: 3.5, level: "moderate", label: "Moderate" },
    { score: 4.0, level: "high", label: "High" },
    { score: 4.5, level: "high", label: "High" },
  ]
  const days = []
  for (let i = 0; i < 7; i++) {
    const d = new Date(now)
    d.setDate(d.getDate() + i)
    const dateStr = toLocalDateStr(d)
    const risk = levels[i % levels.length]
    days.push({
      date: dateStr,
      risk: { score: toFloatScore(risk.score), level: risk.level, label: risk.label },
      activeRiskFactors: [],
    })
  }
  const body: { start: string; days: typeof days; fromModel: false; fallbackReason?: string } = {
    start,
    days,
    fromModel: false,
  }
  if (process.env.NODE_ENV === "development" && debugStderr) {
    body.fallbackReason = debugStderr
  }
  return NextResponse.json(body)
}

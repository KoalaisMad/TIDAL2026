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
  ]
  for (const dir of candidates) {
    const scriptPath = path.join(dir, "asthma-forecaster", "apps", "D A T A", "predict_personalized.py")
    const modelPath = path.join(dir, "asthma-forecaster", "apps", "D A T A", "flare_model.joblib")
    if (fs.existsSync(scriptPath) && fs.existsSync(modelPath)) return dir
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

/** Ensure score is a float with one decimal place. */
function toFloatScore(n: number): number {
  return Math.round(Number(n) * 10) / 10
}

/** Map risk 1–5 or flare_day 0/1 to { score, level, label } */
function toRiskDisplay(value: number, targetCol: "risk" | "flare_day"): { score: number; level: string; label: string } {
  if (targetCol === "flare_day") {
    const level = value === 1 ? "high" : "low"
    return {
      score: toFloatScore(value === 1 ? 4 : 1.5),
      level,
      label: level === "high" ? "High" : "Low",
    }
  }
  const score = toFloatScore(Math.min(5, Math.max(1, value)))
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

  const scriptPath = path.join(tidalRoot, "asthma-forecaster", "apps", "D A T A", "predict_personalized.py")
  if (!fs.existsSync(scriptPath)) {
    return fallbackDays()
  }

  const py = process.platform === "win32" ? "python" : "python3"
  const result = spawnSync(py, [scriptPath, "--out", "-", "--days", "7"], {
    cwd: tidalRoot,
    encoding: "utf-8",
    env: {
      ...process.env,
      PYTHONPATH: path.join(tidalRoot, "asthma-forecaster"),
      MONGODB_DB_NAME: process.env.MONGODB_DB_NAME || "asthma",
    },
    timeout: 60000,
  })

  const stdout = typeof result.stdout === "string" ? result.stdout.trim() : ""
  if (result.status !== 0 || !stdout) {
    return fallbackDays()
  }

  let list: Array<{ user_id: string; date: string; risk?: number; flare_day?: number }>
  try {
    list = JSON.parse(stdout) as typeof list
  } catch {
    return fallbackDays()
  }

  const forUser = userId ? list.filter((p) => String(p.user_id) === String(userId)) : list
  const hasRisk = forUser.some((p) => p.risk != null)
  const targetCol = hasRisk ? "risk" : "flare_day"

  const days = forUser
    .sort((a, b) => a.date.localeCompare(b.date))
    .slice(0, 7)
    .map((p) => {
      const value = (p.risk ?? p.flare_day ?? 1) as number
      const risk = toRiskDisplay(value, targetCol)
      return {
        date: p.date,
        risk: { score: toFloatScore(risk.score), level: risk.level, label: risk.label },
        activeRiskFactors: [] as Array<{ id: string; label: string; iconKey: string }>,
      }
    })

  const start = days[0]?.date ?? new Date().toISOString().slice(0, 10)
  return NextResponse.json({ start, days, fromModel: true })
}

function fallbackDays() {
  const start = new Date().toISOString().slice(0, 10)
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
    const d = new Date(start)
    d.setDate(d.getDate() + i)
    const dateStr = d.toISOString().slice(0, 10)
    const risk = levels[i % levels.length]
    days.push({
      date: dateStr,
      risk: { score: toFloatScore(risk.score), level: risk.level, label: risk.label },
      activeRiskFactors: [],
    })
  }
  return NextResponse.json({ start, days, fromModel: false })
}

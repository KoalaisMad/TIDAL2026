import { NextResponse } from "next/server";
// --- Basic in-memory rate limiting (per IP) ---
const RATE_LIMIT_WINDOW_MS = 60 * 1000; // 1 minute
const RATE_LIMIT_MAX = 10; // max requests per window
const rateLimitMap = new Map();

// --- Simple API key check (optional, for demo) ---
const VALID_API_KEY = process.env.RECOMMENDATIONS_API_KEY || "demo-key";
import { DUMMY_RECOMMENDATIONS, isIsoDate } from "../_mock";
import { getGeminiRecommendations } from "@/lib/gemini";
import { getUserByEmail } from "@/lib/users";

export async function GET(request: Request) {
  // --- Rate limiting ---
  const ip = request.headers.get("x-forwarded-for") || "unknown";
  const now = Date.now();
  let entry = rateLimitMap.get(ip);
  if (!entry || now - entry.start > RATE_LIMIT_WINDOW_MS) {
    entry = { count: 1, start: now };
  } else {
    entry.count++;
  }
  rateLimitMap.set(ip, entry);
  if (entry.count > RATE_LIMIT_MAX) {
    return NextResponse.json({ error: "Rate limit exceeded. Please try again later." }, { status: 429 });
  }

  // --- API key check (optional) ---
  const apiKey = request.headers.get("x-api-key");
  if (VALID_API_KEY && apiKey !== VALID_API_KEY) {
    return NextResponse.json({ error: "Unauthorized: invalid API key." }, { status: 401 });
  }
  const url = new URL(request.url);
  const date = url.searchParams.get("date");
  const riskScoreRaw = url.searchParams.get("riskScore");
  const email = url.searchParams.get("email");
  const activeRiskFactorsRaw = url.searchParams.get("activeRiskFactors");

  if (!isIsoDate(date)) {
    return NextResponse.json(
      { error: "Missing or invalid `date` (expected YYYY-MM-DD)." },
      { status: 400 }
    );
  }

  // Parse and validate riskScore (should be 0-5)
  const riskScore = riskScoreRaw !== null ? parseFloat(riskScoreRaw) : NaN;
  if (isNaN(riskScore) || riskScore < 0 || riskScore > 5) {
    return NextResponse.json(
      { error: "Missing or invalid `riskScore` (expected number 0-5)." },
      { status: 400 }
    );
  }

  // Map riskScore to riskLevel
  let riskLevel: "low" | "moderate" | "high";
  if (riskScore < 2) {
    riskLevel = "low";
  } else if (riskScore < 4) {
    riskLevel = "moderate";
  } else {
    riskLevel = "high";
  }

  // Parse activeRiskFactors (expecting a JSON array or comma-separated string)
  let activeRiskFactors: string[] = [];
  if (activeRiskFactorsRaw) {
    try {
      if (activeRiskFactorsRaw.trim().startsWith("[") && activeRiskFactorsRaw.trim().endsWith("]")) {
        activeRiskFactors = JSON.parse(activeRiskFactorsRaw);
      } else {
        activeRiskFactors = activeRiskFactorsRaw.split(",").map(f => f.trim()).filter(Boolean);
      }
    } catch {
      activeRiskFactors = [];
    }
  }

  // Fetch user profile if email is provided
  let userProfile = null;
  if (email) {
    const user = await getUserByEmail(email);
    userProfile = user?.profile || null;
  }

  // Compose prompt for Gemini
  let prompt = `Generate 3 asthma recommendations for a user with risk level '${riskLevel}' (numeric risk score: ${riskScore}) on ${date}.`;
  if (activeRiskFactors.length > 0) {
    prompt += ` The user's active risk factors are: ${JSON.stringify(activeRiskFactors)}.`;
  }
  if (userProfile) {
    prompt += ` The user's profile is: ${JSON.stringify(userProfile)}.`;
  }
  prompt += ` Format as JSON array with id, title, description.`;

  try {
    const geminiRes = await getGeminiRecommendations({ prompt });
    // Try to parse Gemini response
    const text = geminiRes?.candidates?.[0]?.content?.parts?.[0]?.text || "";
    let recommendations = DUMMY_RECOMMENDATIONS;
    try {
      const parsed = JSON.parse(text);
      if (Array.isArray(parsed)) {
        recommendations = parsed;
      }
    } catch {}
    return NextResponse.json({ date, riskScore, riskLevel, activeRiskFactors, recommendations });
  } catch (err) {
    // Fallback to static recommendations
    return NextResponse.json({ date, riskScore, riskLevel, activeRiskFactors, recommendations: DUMMY_RECOMMENDATIONS });
  }
}


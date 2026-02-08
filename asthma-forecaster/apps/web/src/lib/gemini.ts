// Utility to call Gemini API for recommendations
// Place your Gemini API key in .env as GEMINI_API_KEY

const GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:generateContent";

export async function getGeminiRecommendations({ prompt, apiKey }: { prompt: string; apiKey?: string }) {
  const key = apiKey || process.env.GEMINI_API_KEY;
  if (!key) throw new Error("Missing Gemini API key");

  const body = {
    contents: [{ parts: [{ text: prompt }] }],
  };

  const res = await fetch(`${GEMINI_API_URL}?key=${key}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });

  if (!res.ok) {
    throw new Error(`Gemini API error: ${res.status} ${await res.text()}`);
  }
  return res.json();
}

import { NextResponse } from "next/server"

const ELEVENLABS_TTS_URL = "https://api.elevenlabs.io/v1/text-to-speech"
/** Default voice: Rachel - professional, multilingual */
const DEFAULT_VOICE_ID = "21m00Tcm4TlvDq8ikWAM"
const DEFAULT_MODEL = "eleven_multilingual_v2"

export async function POST(request: Request) {
  const apiKey = process.env.ELEVEN_LABS ?? process.env.ELEVENLABS_API_KEY
  if (!apiKey?.trim()) {
    return NextResponse.json(
      { error: "ElevenLabs API key not configured (ELEVEN_LABS or ELEVENLABS_API_KEY)." },
      { status: 500 }
    )
  }

  let body: { text?: string; voice_id?: string; model_id?: string }
  try {
    body = await request.json()
  } catch {
    return NextResponse.json({ error: "Invalid JSON body." }, { status: 400 })
  }

  const text = typeof body?.text === "string" ? body.text.trim() : ""
  if (!text) {
    return NextResponse.json({ error: "Missing or empty text." }, { status: 400 })
  }

  const voiceId = typeof body?.voice_id === "string" ? body.voice_id : DEFAULT_VOICE_ID
  const modelId = typeof body?.model_id === "string" ? body.model_id : DEFAULT_MODEL

  const url = `${ELEVENLABS_TTS_URL}/${encodeURIComponent(voiceId)}`
  const payload = {
    text,
    model_id: modelId,
    voice_settings: { stability: 0.5, similarity_boost: 0.75 },
  }

  let res: Response
  try {
    res = await fetch(url, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "xi-api-key": apiKey,
        Accept: "audio/mpeg",
      },
      body: JSON.stringify(payload),
    })
  } catch (err) {
    console.error("[api/voice/tts] ElevenLabs request failed:", err)
    return NextResponse.json(
      { error: "Failed to generate speech. Please try again." },
      { status: 502 }
    )
  }

  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    console.error("[api/voice/tts] ElevenLabs error:", res.status, err)
    return NextResponse.json(
      { error: err?.detail?.message ?? "Text-to-speech failed." },
      { status: res.status >= 500 ? 502 : res.status }
    )
  }

  const audioBuffer = await res.arrayBuffer()
  return new NextResponse(audioBuffer, {
    headers: {
      "Content-Type": "audio/mpeg",
      "Cache-Control": "no-store",
    },
  })
}

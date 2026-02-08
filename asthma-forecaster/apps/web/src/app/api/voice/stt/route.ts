import { NextResponse } from "next/server"

const ELEVENLABS_STT_URL = "https://api.elevenlabs.io/v1/speech-to-text"
const STT_MODEL = "scribe_v2"

export async function POST(request: Request) {
  const apiKey = process.env.ELEVEN_LABS ?? process.env.ELEVENLABS_API_KEY
  if (!apiKey?.trim()) {
    return NextResponse.json(
      { error: "ElevenLabs API key not configured (ELEVEN_LABS or ELEVENLABS_API_KEY)." },
      { status: 500 }
    )
  }

  let formData: FormData
  try {
    formData = await request.formData()
  } catch {
    return NextResponse.json({ error: "Invalid form data." }, { status: 400 })
  }

  const file = formData.get("file") ?? formData.get("audio")
  if (!file || !(file instanceof Blob)) {
    return NextResponse.json(
      { error: "Missing audio file. Send a field named 'file' or 'audio'." },
      { status: 400 }
    )
  }

  const body = new FormData()
  body.append("file", file)
  body.append("model_id", STT_MODEL)

  let res: Response
  try {
    res = await fetch(ELEVENLABS_STT_URL, {
      method: "POST",
      headers: {
        "xi-api-key": apiKey,
      },
      body,
    })
  } catch (err) {
    console.error("[api/voice/stt] ElevenLabs request failed:", err)
    return NextResponse.json(
      { error: "Failed to transcribe. Please try again." },
      { status: 502 }
    )
  }

  const data = await res.json().catch(() => ({}))
  if (!res.ok) {
    console.error("[api/voice/stt] ElevenLabs error:", res.status, data)
    return NextResponse.json(
      { error: data?.detail?.message ?? "Speech-to-text failed." },
      { status: res.status >= 500 ? 502 : res.status }
    )
  }

  const text = typeof data?.text === "string" ? data.text.trim() : ""
  return NextResponse.json({ text })
}

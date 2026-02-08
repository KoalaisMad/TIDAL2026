"use client"

import * as React from "react"
import { MessageCircle, Send, Bot, Mic, Square, Volume2, Loader2 } from "lucide-react"

import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { cn } from "@/lib/utils"

export type WeekDayDataForChat = {
  date: string
  risk: { score: number; level: string; label: string }
  activeRiskFactors?: Array<{ id: string; label: string; iconKey?: string }>
  daily?: {
    date?: string
    day_of_week?: string
    season?: string
    AQI?: number | null
    PM2_5_mean?: number | null
    PM2_5_max?: number | null
    temp_min?: number | null
    temp_max?: number | null
    humidity?: number | null
    pollen_tree?: number | null
    pollen_grass?: number | null
    pollen_weed?: number | null
    [key: string]: unknown
  }
}

type ChatMessage = { role: "user" | "model"; content: string }

type AllergyChatbotProps = {
  /** Week forecast data keyed by date (YYYY-MM-DD). Passed as context to the assistant. */
  weekData: Map<string, WeekDayDataForChat>
  /** Optional start date of the week for context */
  weekStart?: string
  /** Optional: show compact header */
  compact?: boolean
  className?: string
}

export function AllergyChatbot({
  weekData,
  weekStart,
  compact = false,
  className,
}: AllergyChatbotProps) {
  const [messages, setMessages] = React.useState<ChatMessage[]>([])
  const [input, setInput] = React.useState("")
  const [loading, setLoading] = React.useState(false)
  const [error, setError] = React.useState<string | null>(null)
  const [isRecording, setIsRecording] = React.useState(false)
  const [playingIndex, setPlayingIndex] = React.useState<number | null>(null)
  const [voiceError, setVoiceError] = React.useState<string | null>(null)
  const scrollRef = React.useRef<HTMLDivElement>(null)
  const mediaRecorderRef = React.useRef<MediaRecorder | null>(null)
  const audioRef = React.useRef<HTMLAudioElement | null>(null)

  const weekContext = React.useMemo(() => {
    const days = Array.from(weekData.entries())
      .sort(([a], [b]) => a.localeCompare(b))
      .map(([, d]) => d)
    return { start: weekStart ?? days[0]?.date, days }
  }, [weekData, weekStart])

  React.useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" })
  }, [messages])

  const sendMessage = React.useCallback(async () => {
    const text = input.trim()
    if (!text || loading) return
    setInput("")
    const userMessage: ChatMessage = { role: "user", content: text }
    setMessages((prev) => [...prev, userMessage])
    setLoading(true)
    setError(null)
    setVoiceError(null)
    try {
      const res = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          messages: [...messages, userMessage].map((m) => ({
            role: m.role,
            content: m.content,
          })),
          weekContext,
        }),
      })
      const data = await res.json().catch(() => ({}))
      if (!res.ok) {
        setError(data?.error ?? "Something went wrong. Please try again.")
        return
      }
      const reply = typeof data?.reply === "string" ? data.reply : ""
      if (reply) {
        setMessages((prev) => [...prev, { role: "model", content: reply }])
      }
    } catch {
      setError("Could not reach the assistant. Please try again.")
    } finally {
      setLoading(false)
    }
  }, [input, loading, messages, weekContext])

  const startRecording = React.useCallback(async () => {
    setVoiceError(null)
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      const recorder = new MediaRecorder(stream)
      const chunks: BlobPart[] = []
      recorder.ondataavailable = (e) => {
        if (e.data.size) chunks.push(e.data)
      }
      recorder.onstop = async () => {
        stream.getTracks().forEach((t) => t.stop())
        if (chunks.length === 0) return
        const blob = new Blob(chunks, { type: "audio/webm" })
        const formData = new FormData()
        formData.append("file", blob, "recording.webm")
        try {
          const res = await fetch("/api/voice/stt", { method: "POST", body: formData })
          const data = await res.json().catch(() => ({}))
          if (!res.ok) {
            setVoiceError(data?.error ?? "Could not transcribe. Try again.")
            return
          }
          const text = typeof data?.text === "string" ? data.text.trim() : ""
          if (text) setInput((prev) => (prev ? `${prev} ${text}` : text))
        } catch {
          setVoiceError("Voice input failed. Please try again.")
        }
      }
      recorder.start()
      mediaRecorderRef.current = recorder
      setIsRecording(true)
    } catch {
      setVoiceError("Microphone access denied or unavailable.")
    }
  }, [])

  const stopRecording = React.useCallback(() => {
    const recorder = mediaRecorderRef.current
    if (recorder?.state === "recording") {
      recorder.stop()
      mediaRecorderRef.current = null
    }
    setIsRecording(false)
  }, [])

  const toggleRecording = React.useCallback(() => {
    if (isRecording) stopRecording()
    else startRecording()
  }, [isRecording, startRecording, stopRecording])

  const playReply = React.useCallback(async (text: string, index: number) => {
    if (!text.trim() || playingIndex !== null) return
    setVoiceError(null)
    setPlayingIndex(index)
    try {
      const res = await fetch("/api/voice/tts", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text }),
      })
      if (!res.ok) {
        const data = await res.json().catch(() => ({}))
        setVoiceError(data?.error ?? "Could not play speech.")
        setPlayingIndex(null)
        return
      }
      const blob = await res.blob()
      const url = URL.createObjectURL(blob)
      const audio = new Audio(url)
      audioRef.current = audio
      audio.onended = () => {
        URL.revokeObjectURL(url)
        audioRef.current = null
        setPlayingIndex(null)
      }
      audio.onerror = () => {
        URL.revokeObjectURL(url)
        setPlayingIndex(null)
      }
      await audio.play()
    } catch {
      setVoiceError("Could not play reply.")
      setPlayingIndex(null)
    }
  }, [playingIndex])

  React.useEffect(() => {
    return () => {
      if (audioRef.current) {
        audioRef.current.pause()
        audioRef.current = null
      }
    }
  }, [])

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault()
      sendMessage()
    }
  }

  const hasContext = weekContext.days.length > 0

  return (
    <Card className={cn("overflow-hidden", className)}>
      <CardHeader className="pb-3">
        <CardTitle className={cn("flex items-center gap-2 text-lg", compact && "text-base")}>
          <MessageCircle className="size-5 text-primary" aria-hidden />
          Allergy & asthma assistant
        </CardTitle>
        {!compact && (
          <p className="text-muted-foreground text-sm">
            Ask about allergies and risk for the coming days. Answers use your current week forecast when available.
          </p>
        )}
      </CardHeader>
      <CardContent className="space-y-4 pt-0">
        <div
          ref={scrollRef}
          className="flex max-h-[320px] min-h-[160px] flex-col gap-3 overflow-y-auto rounded-2xl border bg-muted/40 p-3"
          aria-label="Chat messages"
        >
          {messages.length === 0 && (
            <div className="text-muted-foreground flex flex-1 flex-col items-center justify-center gap-2 rounded-xl border border-dashed border-muted-foreground/20 bg-background/50 p-4 text-center text-sm">
              {hasContext ? (
                <>
                  <Bot className="size-8" aria-hidden />
                  <p>Ask things like: &ldquo;Which day this week is riskiest?&rdquo; or &ldquo;How should I prepare for high pollen?&rdquo;</p>
                </>
              ) : (
                <>
                  <Bot className="size-8" aria-hidden />
                  <p>Load the week forecast above, then ask about allergies and how to respond.</p>
                </>
              )}
            </div>
          )}
          {messages.map((msg, i) => (
            <div
              key={i}
              className={cn(
                "flex gap-2",
                msg.role === "user" ? "justify-end" : "justify-start"
              )}
            >
              {msg.role === "model" && (
                <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-primary/15 text-primary" aria-hidden>
                  <Bot className="size-4" />
                </span>
              )}
              <div
                className={cn(
                  "max-w-[85%] rounded-2xl px-4 py-2.5 text-sm",
                  msg.role === "user"
                    ? "bg-primary text-primary-foreground"
                    : "bg-card text-card-foreground shadow-md"
                )}
              >
                <div className="flex items-start gap-2">
                  <p className="whitespace-pre-wrap flex-1">{msg.content}</p>
                  {msg.role === "model" && (
                    <Button
                      type="button"
                      variant="ghost"
                      size="icon"
                      className="h-8 w-8 shrink-0 rounded-full text-muted-foreground hover:text-foreground"
                      onClick={() => playReply(msg.content, i)}
                      disabled={playingIndex !== null}
                      aria-label="Play reply"
                    >
                      {playingIndex === i ? (
                        <Loader2 className="size-4 animate-spin" />
                      ) : (
                        <Volume2 className="size-4" />
                      )}
                    </Button>
                  )}
                </div>
              </div>
            </div>
          ))}
          {loading && (
            <div className="flex justify-start gap-2">
              <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-primary/15 text-primary" aria-hidden>
                <Bot className="size-4" />
              </span>
              <div className="rounded-2xl bg-card px-4 py-2.5 text-sm text-muted-foreground">
                Thinking…
              </div>
            </div>
          )}
        </div>
        {(error || voiceError) && (
          <p className="text-destructive text-sm" role="alert">
            {error ?? voiceError}
          </p>
        )}
        <div className="flex gap-2">
          <Button
            type="button"
            variant={isRecording ? "destructive" : "outline"}
            size="icon"
            className="shrink-0 rounded-2xl"
            onClick={toggleRecording}
            disabled={loading}
            aria-label={isRecording ? "Stop recording" : "Voice input"}
          >
            {isRecording ? (
              <Square className="size-4" />
            ) : (
              <Mic className="size-4" />
            )}
          </Button>
          <Input
            placeholder="Ask about this week’s allergy risk…"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            disabled={loading}
            aria-label="Chat message"
            className="rounded-2xl"
          />
          <Button
            type="button"
            size="default"
            className="shrink-0 rounded-2xl"
            onClick={sendMessage}
            disabled={loading || !input.trim()}
            aria-label="Send message"
          >
            <Send className="size-4" />
          </Button>
        </div>
      </CardContent>
    </Card>
  )
}

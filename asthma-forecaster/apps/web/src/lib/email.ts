import { Resend } from "resend"

const resendApiKey = process.env.RESEND_API_KEY
const fromEmail = process.env.EMAIL_FROM || "Breathe Well <onboarding@resend.dev>"

/**
 * Send a high-risk asthma alert email for the next day.
 * No-op if RESEND_API_KEY is not set.
 */
export async function sendHighRiskAlert(
  to: string,
  options: { name?: string; date: string; riskLabel?: string }
): Promise<{ ok: boolean; error?: string }> {
  if (!resendApiKey?.trim()) {
    return { ok: false, error: "RESEND_API_KEY not configured" }
  }

  const displayName = options.name?.trim() || "there"
  const dateLabel = options.date
  const riskLabel = options.riskLabel ?? "High"

  const resend = new Resend(resendApiKey)
  const { error } = await resend.emails.send({
    from: fromEmail,
    to: [to],
    subject: `Breathe Well: ${riskLabel} asthma risk for ${dateLabel}`,
    html: `
      <p>Hi ${displayName},</p>
      <p>Your Breathe Well asthma risk forecast shows <strong>${riskLabel} risk</strong> for ${dateLabel}.</p>
      <p>Consider limiting prolonged outdoor activity and keeping your rescue inhaler handy.</p>
      <p>View your full forecast: <a href="${process.env.NEXTAUTH_URL || "http://127.0.0.1:3000"}/breathe-well/environmental">Breathe Well dashboard</a></p>
      <p>— Breathe Well</p>
    `,
  })

  if (error) return { ok: false, error: String(error) }
  return { ok: true }
}

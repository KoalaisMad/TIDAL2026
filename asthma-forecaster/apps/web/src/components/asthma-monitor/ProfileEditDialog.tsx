"use client"

import * as React from "react"
import { useSession } from "next-auth/react"

import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { parseHeightToMeters, parseWeightToKg, computeBmi, bmiCategory } from "@/lib/bmi"

interface UserProfile {
  name?: string
  height?: string
  weight?: string
  gender?: string
  smokerStatus?: string
  petExposure?: string
  bmi?: number
}

interface ProfileEditDialogProps {
  open: boolean
  onClose: () => void
  onSaved: () => void
}

export function ProfileEditDialog({ open, onClose, onSaved }: ProfileEditDialogProps) {
  const { data: session } = useSession()
  const [formData, setFormData] = React.useState({
    name: "",
    height: "",
    weight: "",
    gender: "",
    smokerStatus: "",
    petExposure: "",
  })
  const [loading, setLoading] = React.useState(false)
  const [saving, setSaving] = React.useState(false)
  const [error, setError] = React.useState<string | null>(null)
  const dialogRef = React.useRef<HTMLDialogElement>(null)

  const bmi = React.useMemo(
    () => computeBmi(parseHeightToMeters(formData.height), parseWeightToKg(formData.weight)),
    [formData.height, formData.weight]
  )

  React.useEffect(() => {
    const el = dialogRef.current
    if (!el) return
    if (open) {
      el.showModal()
      setError(null)
      setLoading(true)
      fetch("/api/users/me")
        .then((res) => res.json())
        .then((data: { profile?: UserProfile; name?: string }) => {
          const p = data.profile ?? {}
          setFormData({
            name: data.name ?? p.name ?? session?.user?.name ?? "",
            height: p.height ?? "",
            weight: p.weight ?? "",
            gender: p.gender ?? "",
            smokerStatus: p.smokerStatus ?? "",
            petExposure: p.petExposure ?? "",
          })
        })
        .catch(() => setError("Could not load profile"))
        .finally(() => setLoading(false))
    } else {
      el.close()
    }
  }, [open, session?.user?.name])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!formData.name.trim()) {
      setError("Please enter your name")
      return
    }
    setError(null)
    setSaving(true)
    try {
      const res = await fetch("/api/users/register", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: formData.name.trim(),
          height: formData.height.trim() || undefined,
          weight: formData.weight.trim() || undefined,
          gender: formData.gender || undefined,
          smokerStatus: formData.smokerStatus || undefined,
          petExposure: formData.petExposure || undefined,
          ...(bmi != null && { bmi }),
        }),
      })
      if (!res.ok) {
        const data = await res.json().catch(() => ({}))
        throw new Error(data.error ?? "Failed to save")
      }
      if (typeof window !== "undefined") {
        window.dispatchEvent(new CustomEvent("profile-updated", { detail: { name: formData.name.trim() } }))
      }
      onSaved()
      onClose()
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save")
    } finally {
      setSaving(false)
    }
  }

  const handleBackdropClick = (e: React.MouseEvent<HTMLDialogElement>) => {
    if (e.target === dialogRef.current) onClose()
  }

  return (
    <dialog
      ref={dialogRef}
      onCancel={onClose}
      onClick={handleBackdropClick}
      className="fixed left-1/2 top-1/2 z-50 max-h-[90dvh] w-full max-w-md -translate-x-1/2 -translate-y-1/2 rounded-2xl border-0 bg-card p-0 shadow-xl backdrop:bg-black/40 [&::backdrop]:bg-black/40"
      aria-labelledby="profile-edit-title"
    >
      <form onSubmit={handleSubmit} className="flex max-h-[90dvh] flex-col p-6">
        <h2 id="profile-edit-title" className="text-xl font-bold">
          Edit profile
        </h2>
        <p className="mt-1 text-sm text-muted-foreground">
          Your profile is stored in your account and used for personalized risk.
        </p>

        {loading ? (
          <p className="mt-6 py-4 text-sm text-muted-foreground">Loading…</p>
        ) : (
          <div className="mt-6 space-y-4 overflow-y-auto">
            {error && (
              <p className="text-sm text-destructive" role="alert">
                {error}
              </p>
            )}
            <div className="space-y-2">
              <label htmlFor="profile-name" className="text-sm font-semibold">
                Name
              </label>
              <Input
                id="profile-name"
                type="text"
                placeholder="Your name"
                value={formData.name}
                onChange={(e) => setFormData((p) => ({ ...p, name: e.target.value }))}
                required
                className="bg-white"
              />
            </div>
            <div className="space-y-2">
              <label htmlFor="profile-height" className="text-sm font-semibold">
                Height <span className="font-normal text-muted-foreground">(for BMI)</span>
              </label>
              <Input
                id="profile-height"
                type="text"
                placeholder="e.g. 5'8&quot; or 173 cm"
                value={formData.height}
                onChange={(e) => setFormData((p) => ({ ...p, height: e.target.value }))}
                className="bg-white"
              />
            </div>
            <div className="space-y-2">
              <label htmlFor="profile-weight" className="text-sm font-semibold">
                Weight <span className="font-normal text-muted-foreground">(for BMI)</span>
              </label>
              <Input
                id="profile-weight"
                type="text"
                placeholder="e.g. 150 lbs or 68 kg"
                value={formData.weight}
                onChange={(e) => setFormData((p) => ({ ...p, weight: e.target.value }))}
                className="bg-white"
              />
              {bmi != null && (
                <p className="text-sm text-muted-foreground">
                  BMI: <span className="font-semibold text-foreground">{bmi}</span> ({bmiCategory(bmi)})
                </p>
              )}
            </div>
            <div className="space-y-2">
              <label htmlFor="profile-gender" className="text-sm font-semibold">
                Gender
              </label>
              <Select
                value={formData.gender}
                onValueChange={(v) => setFormData((p) => ({ ...p, gender: v }))}
              >
                <SelectTrigger id="profile-gender" className="bg-white">
                  <SelectValue placeholder="Select" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="male">Male</SelectItem>
                  <SelectItem value="female">Female</SelectItem>
                  <SelectItem value="non-binary">Non-binary</SelectItem>
                  <SelectItem value="prefer-not-to-say">Prefer not to say</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <label htmlFor="profile-smoker" className="text-sm font-semibold">
                Smoker status
              </label>
              <Select
                value={formData.smokerStatus}
                onValueChange={(v) => setFormData((p) => ({ ...p, smokerStatus: v }))}
              >
                <SelectTrigger id="profile-smoker" className="bg-white">
                  <SelectValue placeholder="Select" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="smoker">I am a smoker</SelectItem>
                  <SelectItem value="exposed">Often around smokers</SelectItem>
                  <SelectItem value="none">No smoking exposure</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <label htmlFor="profile-pet" className="text-sm font-semibold">
                Pet exposure
              </label>
              <Select
                value={formData.petExposure}
                onValueChange={(v) => setFormData((p) => ({ ...p, petExposure: v }))}
              >
                <SelectTrigger id="profile-pet" className="bg-white">
                  <SelectValue placeholder="Select" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="yes">Yes, I have or am around pets</SelectItem>
                  <SelectItem value="no">No pet exposure</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>
        )}

        <div className="mt-6 flex shrink-0 gap-3">
          <Button type="button" variant="outline" size="pill" onClick={onClose} className="flex-1">
            Cancel
          </Button>
          <Button type="submit" size="pill" disabled={loading || saving} className="flex-1">
            {saving ? "Saving…" : "Save"}
          </Button>
        </div>
      </form>
    </dialog>
  )
}

"use client"

import * as React from "react"
import { useRouter } from "next/navigation"
import { useSession } from "next-auth/react"

import { Button } from "@/components/ui/button"
import { Card } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { layout } from "@/theme"
import { cn } from "@/lib/utils"

export default function RegistrationPage() {
  const router = useRouter()
  const { data: session, status } = useSession()
  const [formData, setFormData] = React.useState({
    name: "",
    height: "",
    weight: "",
    gender: "",
  })
  const [submitting, setSubmitting] = React.useState(false)
  const [error, setError] = React.useState<string | null>(null)

  // Require auth; prefill name from session
  React.useEffect(() => {
    if (status === "unauthenticated") {
      router.replace("/auth/signin?callbackUrl=" + encodeURIComponent("/breathe-well/registration"))
      return
    }
    if (status === "authenticated" && session?.user?.name && !formData.name) {
      setFormData((prev) => ({ ...prev, name: session.user.name ?? "" }))
    }
  }, [status, session?.user?.name, router, formData.name])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!formData.name.trim()) {
      setError("Please enter your name")
      return
    }
    setError(null)
    setSubmitting(true)
    try {
      const res = await fetch("/api/users/register", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: formData.name.trim(),
          height: formData.height.trim() || undefined,
          weight: formData.weight.trim() || undefined,
          gender: formData.gender || undefined,
        }),
      })
      if (!res.ok) {
        const data = await res.json().catch(() => ({}))
        throw new Error(data.error ?? "Registration failed")
      }
      router.push("/breathe-well/environmental")
    } catch (err) {
      setError(err instanceof Error ? err.message : "Registration failed")
      setSubmitting(false)
    }
  }

  return (
    <div className={layout.pageBg}>
      <main className={layout.container}>
        <div className="flex min-h-[calc(100dvh-8rem)] items-center justify-center py-8">
          <Card className="w-full max-w-md">
            <form onSubmit={handleSubmit} className="p-8 space-y-8">
              {error && (
                <p className="text-sm text-destructive" role="alert">
                  {error}
                </p>
              )}
              {/* Header Section */}
              <div className="space-y-2">
                <p className="text-sm font-light text-muted-foreground">
                  Welcome,
                </p>
                <h1 className="text-3xl font-bold tracking-tight">
                  Get Started
                </h1>
                <p className="text-base text-muted-foreground leading-relaxed pt-2">
                  Get personalized asthma flare-up predictions tailored to your
                  unique profile. Your information helps us provide more
                  accurate risk assessments and timely alerts.
                </p>
              </div>

              {/* Form Fields */}
              <div className="space-y-6">
                {/* Name Field */}
                <div className="space-y-2">
                  <label
                    htmlFor="name"
                    className="text-sm font-semibold text-foreground"
                  >
                    Name
                  </label>
                  <Input
                    id="name"
                    type="text"
                    placeholder="Enter your name"
                    value={formData.name}
                    onChange={(e) =>
                      setFormData({ ...formData, name: e.target.value })
                    }
                    required
                  />
                </div>

                {/* Height Field */}
                <div className="space-y-2">
                  <label
                    htmlFor="height"
                    className="text-sm font-semibold text-foreground"
                  >
                    Height{" "}
                    <span className="font-normal text-muted-foreground">
                      (Optional)
                    </span>
                  </label>
                  <Input
                    id="height"
                    type="text"
                    placeholder="e.g., 5'8&quot; or 173 cm"
                    value={formData.height}
                    onChange={(e) =>
                      setFormData({ ...formData, height: e.target.value })
                    }
                  />
                </div>

                {/* Weight Field */}
                <div className="space-y-2">
                  <label
                    htmlFor="weight"
                    className="text-sm font-semibold text-foreground"
                  >
                    Weight{" "}
                    <span className="font-normal text-muted-foreground">
                      (Optional)
                    </span>
                  </label>
                  <Input
                    id="weight"
                    type="text"
                    placeholder="e.g., 150 lbs or 68 kg"
                    value={formData.weight}
                    onChange={(e) =>
                      setFormData({ ...formData, weight: e.target.value })
                    }
                  />
                </div>

                {/* Gender Field */}
                <div className="space-y-2">
                  <label
                    htmlFor="gender"
                    className="text-sm font-semibold text-foreground"
                  >
                    Gender{" "}
                    <span className="font-normal text-muted-foreground">
                      (Optional)
                    </span>
                  </label>
                  <Select
                    value={formData.gender}
                    onValueChange={(value: string) =>
                      setFormData({ ...formData, gender: value })
                    }
                  >
                    <SelectTrigger id="gender">
                      <SelectValue placeholder="Select gender" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="male">Male</SelectItem>
                      <SelectItem value="female">Female</SelectItem>
                      <SelectItem value="non-binary">Non-binary</SelectItem>
                      <SelectItem value="prefer-not-to-say">
                        Prefer not to say
                      </SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              </div>

              {/* Submit Button */}
              <Button
                type="submit"
                size="pill"
                className="w-full"
                disabled={submitting}
              >
                {submitting ? "Saving…" : "Create Account"}
              </Button>
            </form>
          </Card>
        </div>
      </main>
    </div>
  )
}

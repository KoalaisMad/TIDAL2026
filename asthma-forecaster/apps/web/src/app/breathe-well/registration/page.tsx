"use client"

import * as React from "react"
import { useRouter } from "next/navigation"

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
  const [formData, setFormData] = React.useState({
    name: "",
    height: "",
    weight: "",
    gender: "",
  })

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    
    // Basic validation
    if (!formData.name.trim()) {
      alert("Please enter your name")
      return
    }

    // TODO: Save user data to backend/localStorage
    console.log("Registration data:", formData)
    
    // Navigate to the main app
    router.push("/breathe-well/environmental")
  }

  return (
    <div className={layout.pageBg}>
      <main className={layout.container}>
        <div className="flex min-h-[calc(100dvh-8rem)] items-center justify-center py-8">
          <Card className="w-full max-w-md">
            <form onSubmit={handleSubmit} className="p-8 space-y-8">
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
                    onValueChange={(value) =>
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
              >
                Create Account
              </Button>
            </form>
          </Card>
        </div>
      </main>
    </div>
  )
}

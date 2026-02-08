"use client"

import * as React from "react"
import { Card } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { useRouter } from "next/navigation"

export function PersonalizedRiskContent() {
  const router = useRouter()

  return (
    <>
      <Card className="p-8">
        <div className="space-y-6">
          <h2 className="text-2xl font-bold">Personalized Risk Assessment</h2>
          <p className="text-base text-muted-foreground leading-relaxed">
            This section will provide personalized asthma risk information based on your
            health profile and triggers.
          </p>
          <div className="rounded-3xl border-2 border-dashed border-muted/50 bg-muted/20 p-12 text-center">
            <p className="text-sm font-medium text-muted-foreground">
              Personalized content coming soon...
            </p>
          </div>
        </div>
      </Card>

      <div className="sticky bottom-6 flex justify-center pt-4 md:static">
        <Button
          size="pill"
          variant="outline"
          className="w-full md:w-fit md:px-12"
          onClick={() => {
            router.push("/asthma-monitor/environmental")
          }}
        >
          Back to Environmental Risk
        </Button>
      </div>
    </>
  )
}

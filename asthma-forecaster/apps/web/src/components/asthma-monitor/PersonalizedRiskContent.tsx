"use client"

import * as React from "react"
import { Card } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { useRouter } from "next/navigation"

export function PersonalizedRiskContent() {
  const router = useRouter()

  return (
    <>
      <Card className="p-6">
        <div className="space-y-4">
          <h2 className="text-xl font-semibold">Personalized Risk Assessment</h2>
          <p className="text-muted-foreground">
            This section will provide personalized asthma risk information based on your
            health profile and triggers.
          </p>
          <div className="rounded-lg border-2 border-dashed border-muted p-8 text-center">
            <p className="text-sm text-muted-foreground">
              Personalized content coming soon...
            </p>
          </div>
        </div>
      </Card>

      <div className="sticky bottom-4 flex justify-center pt-2 md:static">
        <Button
          size="pill"
          variant="outline"
          className="w-full shadow-sm md:w-fit md:px-10"
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

"use client"

import * as React from "react"
import { usePathname, useRouter } from "next/navigation"

import { cn } from "@/lib/utils"
import { layout, spacing } from "@/theme"
import { Header } from "@/components/asthma-monitor/Header"
import { RiskTabs } from "@/components/asthma-monitor/RiskTabs"

export default function AsthmaMonitorLayout({
  children,
}: {
  children: React.ReactNode
}) {
  const pathname = usePathname()
  const router = useRouter()

  // Determine current tab from pathname
  const currentTab = pathname.includes("/personalized")
    ? "personalized"
    : "environmental"

  const handleTabChange = (tab: "environmental" | "personalized") => {
    if (tab === "environmental") {
      router.push("/breathe-well/environmental")
    } else {
      router.push("/breathe-well/personalized")
    }
  }

  return (
    <div className={layout.pageBg}>
      <main className={layout.container}>
        <div className={cn("flex flex-col", spacing.sectionGap)}>
          <Header title="Breathe Well" />
          <RiskTabs value={currentTab} onValueChange={handleTabChange} />
          {children}
        </div>
      </main>
    </div>
  )
}

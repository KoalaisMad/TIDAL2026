"use client"

import * as React from "react"
import { usePathname, useRouter } from "next/navigation"
import { useSession } from "next-auth/react"

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
  const { data: session, status } = useSession()
  const [registrationChecked, setRegistrationChecked] = React.useState(false)

  // Redirect unauthenticated users to sign-in
  React.useEffect(() => {
    if (status === "unauthenticated") {
      router.replace("/auth/signin?callbackUrl=" + encodeURIComponent("/breathe-well"))
      return
    }
  }, [status, router])

  // If session says needsRegistration, verify with backend (in case they just registered)
  React.useEffect(() => {
    if (status !== "authenticated" || !session?.user || registrationChecked) return
    const needsReg = (session as { needsRegistration?: boolean }).needsRegistration
    if (!needsReg) {
      setRegistrationChecked(true)
      return
    }
    if (pathname.includes("/registration")) {
      setRegistrationChecked(true)
      return
    }
    fetch("/api/users/me")
      .then((res) => res.json())
      .then((data) => {
        setRegistrationChecked(true)
        if (!data.registered) {
          router.replace("/breathe-well/registration")
        }
      })
      .catch(() => {
        setRegistrationChecked(true)
        router.replace("/breathe-well/registration")
      })
  }, [session, status, pathname, router, registrationChecked])

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

  if (status === "loading" || (session?.user && !registrationChecked && (session as { needsRegistration?: boolean }).needsRegistration && !pathname.includes("/registration"))) {
    return (
      <div className={layout.pageBg}>
        <main className={layout.container}>
          <div className="flex min-h-[calc(100dvh-8rem)] items-center justify-center">
            <p className="text-muted-foreground">Loading…</p>
          </div>
        </main>
      </div>
    )
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

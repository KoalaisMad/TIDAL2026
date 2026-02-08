"use client"

import * as React from "react"
import { ArrowLeft, ArrowRight } from "lucide-react"
import { useRouter } from "next/navigation"
import { useSession, signIn } from "next-auth/react"

import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { cn } from "@/lib/utils"

type RiskTabsProps = {
  value: "environmental" | "personalized"
  onValueChange: (v: RiskTabsProps["value"]) => void
  className?: string
}

export function RiskTabs({ value, onValueChange, className }: RiskTabsProps) {
  const router = useRouter()
  const { data: session, status } = useSession()

  const handleTabChange = (newValue: string) => {
    const tabValue = newValue as RiskTabsProps["value"]
    
    // Handle environmental tab - always navigate
    if (tabValue === "environmental") {
      router.push("/breathe-well/environmental")
      onValueChange(tabValue)
      return
    }
    
    // Handle personalized tab - check authentication first
    if (tabValue === "personalized") {
      // If loading, don't do anything yet
      if (status === "loading") {
        return
      }
      
      // If not authenticated, redirect to sign-in with callback
      if (!session) {
        signIn("google", {
          callbackUrl: "/breathe-well/personalized",
        })
        return
      }
      
      // User is authenticated, navigate to personalized page
      router.push("/breathe-well/personalized")
      onValueChange(tabValue)
    }
  }

  const isAuthenticated = status === "authenticated" && !!session

  return (
    <Tabs
      value={value}
      onValueChange={handleTabChange}
      className={cn("w-full", className)}
    >
      <TabsList className="w-full justify-between gap-3 bg-transparent p-0 sm:gap-6">
        <TabsTrigger
          value="environmental"
          className="min-h-10 touch-manipulation rounded-none bg-transparent px-0 text-sm font-medium text-muted-foreground data-[state=active]:bg-transparent data-[state=active]:shadow-none data-[state=active]:text-foreground data-[state=active]:font-bold sm:min-h-0 sm:text-base"
        >
          <span className="inline-flex items-center gap-1.5 sm:gap-2">
            {value === "personalized" && (
              <ArrowLeft className="h-4 w-4 shrink-0 sm:h-5 sm:w-5" aria-hidden="true" />
            )}
            <span className="hidden sm:inline">Environmental Risk</span>
            <span className="sm:hidden">Environmental</span>
          </span>
        </TabsTrigger>

        <TabsTrigger
          value="personalized"
          className={cn(
            "min-h-10 touch-manipulation text-sm font-medium transition-all sm:min-h-0 sm:text-base cursor-pointer",
            isAuthenticated
              ? "rounded-none bg-transparent px-0 text-muted-foreground data-[state=active]:bg-transparent data-[state=active]:shadow-none data-[state=active]:text-foreground data-[state=active]:font-bold"
              : "h-11 px-4 py-3 rounded-3xl bg-primary text-primary-foreground font-semibold shadow-md hover:shadow-lg hover:brightness-110 sm:px-6"
          )}
        >
          {isAuthenticated ? (
            <span className="inline-flex items-center gap-1.5 sm:gap-2">
              <span className="hidden sm:inline">Personalized Risk</span>
              <span className="sm:hidden">Personalized</span>
              <ArrowRight className="h-4 w-4 shrink-0 sm:h-5 sm:w-5" aria-hidden="true" />
            </span>
          ) : (
            <span className="inline-flex items-center gap-2">
              Sign in for Personalized Risk
            </span>
          )}
        </TabsTrigger>
      </TabsList>
    </Tabs>
  )
}


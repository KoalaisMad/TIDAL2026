"use client"

import * as React from "react"
import { useSession, signOut } from "next-auth/react"

export function Header({ title }: { title: string }) {
  const { data: session, status } = useSession()

  return (
    <header className="flex items-center justify-between py-2">
      <div>
        <p className="text-sm font-light text-muted-foreground">Good morning,</p>
        <h1 className="text-2xl font-bold tracking-tight">{title}</h1>
      </div>
      {status === "authenticated" && session?.user && (
        <div className="flex items-center gap-2 sm:gap-3">
          <div className="flex items-center gap-2 rounded-full bg-primary/10 px-3 py-1.5">
            <span
              className="h-2 w-2 shrink-0 rounded-full bg-emerald-500"
              aria-hidden
            />
            <span className="max-w-[120px] truncate text-sm text-muted-foreground sm:max-w-[180px]">
              {session.user.name ?? session.user.email ?? "Logged in"}
            </span>
          </div>
          <button
            type="button"
            onClick={() => signOut({ callbackUrl: "/auth/signin" })}
            className="text-sm text-muted-foreground underline underline-offset-2 hover:text-foreground"
          >
            Sign out
          </button>
        </div>
      )}
      {status !== "authenticated" && (
        <div className="h-10 w-10 rounded-2xl bg-primary/10" aria-hidden />
      )}
    </header>
  )
}


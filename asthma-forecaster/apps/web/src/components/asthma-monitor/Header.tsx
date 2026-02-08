"use client"

import * as React from "react"
import { useSession, signOut } from "next-auth/react"
import { ProfileEditDialog } from "./ProfileEditDialog"

export const PROFILE_UPDATED_EVENT = "profile-updated"

function getInitial(name: string | null | undefined, email: string | null | undefined): string {
  if (name?.trim()) return name.trim().charAt(0).toUpperCase()
  if (email?.trim()) return email.trim().charAt(0).toUpperCase()
  return "?"
}

export function Header({ title }: { title: string }) {
  const { data: session, status } = useSession()
  const [profileOpen, setProfileOpen] = React.useState(false)
  const [savedName, setSavedName] = React.useState<string | null>(null)

  const fetchProfile = React.useCallback(() => {
    fetch("/api/users/me")
      .then((res) => res.json())
      .then((data: { name?: string }) => {
        if (data.name != null) setSavedName(data.name)
      })
      .catch(() => {})
  }, [])

  React.useEffect(() => {
    if (status !== "authenticated") return
    fetchProfile()
  }, [status, fetchProfile])

  React.useEffect(() => {
    const handler = () => fetchProfile()
    window.addEventListener(PROFILE_UPDATED_EVENT, handler)
    return () => window.removeEventListener(PROFILE_UPDATED_EVENT, handler)
  }, [fetchProfile])

  const displayName =
    savedName ?? session?.user?.name ?? session?.user?.email ?? "Logged in"

  return (
    <header className="flex min-w-0 items-center justify-between gap-3 py-2">
      <div className="min-w-0 flex-1">
        <p className="text-xs font-light text-muted-foreground sm:text-sm">Good morning,</p>
        <h1 className="truncate text-xl font-bold tracking-tight sm:text-2xl">
          {status === "authenticated" && displayName ? displayName : title}
        </h1>
      </div>
      {status === "authenticated" && session?.user && (
        <div className="flex shrink-0 items-center gap-2 sm:gap-3">
          <button
            type="button"
            onClick={() => setProfileOpen(true)}
            className="flex items-center gap-2 rounded-full bg-primary/10 px-2 py-1.5 transition-opacity hover:opacity-90 focus:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            aria-label="Open profile"
          >
            {session.user.image ? (
              <img
                src={session.user.image}
                alt=""
                className="h-8 w-8 shrink-0 rounded-full object-cover"
              />
            ) : (
              <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-primary/20 text-sm font-medium text-foreground">
                {getInitial(displayName, session.user.email)}
              </span>
            )}
            <span className="max-w-[120px] truncate text-sm text-muted-foreground sm:max-w-[180px]">
              {displayName}
            </span>
          </button>
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
      <ProfileEditDialog
        open={profileOpen}
        onClose={() => setProfileOpen(false)}
        onSaved={() => setProfileOpen(false)}
      />
    </header>
  )
}


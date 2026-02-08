"use client"

import { useSession, signIn, signOut } from "next-auth/react"

export default function AuthButton() {
  const { data: session, status } = useSession()

  if (status === "loading") {
    return (
      <div className="flex items-center gap-2">
        <div className="h-8 w-8 animate-spin rounded-full border-2 border-gray-300 border-t-blue-600" />
      </div>
    )
  }

  if (session) {
    return (
      <div className="flex items-center gap-4">
        <div className="flex items-center gap-2">
          {session.user?.image && (
            <img
              src={session.user.image}
              alt={session.user.name || "User"}
              className="h-8 w-8 rounded-full"
            />
          )}
          <span className="text-sm font-medium text-gray-700">
            {session.user?.name}
          </span>
        </div>
        <button
          onClick={() => signOut()}
          className="rounded-lg bg-gray-200 px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-300"
        >
          Sign Out
        </button>
      </div>
    )
  }

  return (
    <button
      onClick={() => signIn("google")}
      className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700"
    >
      Sign In
    </button>
  )
}

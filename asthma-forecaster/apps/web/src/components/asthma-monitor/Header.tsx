import * as React from "react"

export function Header({ title }: { title: string }) {
  return (
    <header className="flex items-center justify-between">
      <h1 className="text-lg font-semibold tracking-tight">{title}</h1>
      <div className="h-6 w-6" aria-hidden="true" />
    </header>
  )
}


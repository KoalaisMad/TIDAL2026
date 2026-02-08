import * as React from "react"

export function Header({ title }: { title: string }) {
  return (
    <header className="flex items-center justify-between py-2">
      <div>
        <p className="text-sm font-light text-muted-foreground">Good morning,</p>
        <h1 className="text-2xl font-bold tracking-tight">{title}</h1>
      </div>
      <div className="h-10 w-10 rounded-2xl bg-primary/10" aria-hidden="true" />
    </header>
  )
}


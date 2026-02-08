/**
 * Central theme + spacing tokens.
 *
 * Keep these small and composable. Prefer Tailwind utility classes, but
 * centralize the "layout glue" (padding/gaps/max widths) here so screens feel consistent.
 */
export const layout = {
  /** App page background - warm orangey-peach with subtle gradient */
  pageBg: "min-h-dvh bg-gradient-warm",
  /**
   * Mobile-first container matching the screenshot, with a wider desktop container.
   * This keeps mobile "full" (w-full) while improving browser use of space.
   * Generous whitespace for calm, breathable layout
   */
  container:
    "mx-auto w-full max-w-sm px-6 py-8 md:max-w-5xl md:px-10 md:py-12",
} as const

export const spacing = {
  sectionGap: "gap-8",
  blockGap: "gap-5",
  tightGap: "gap-3",
} as const

export const radii = {
  pill: "rounded-full",
  card: "rounded-3xl",
} as const


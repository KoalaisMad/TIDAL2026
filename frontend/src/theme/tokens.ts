/**
 * Central theme + spacing tokens.
 *
 * Keep these small and composable. Prefer Tailwind utility classes, but
 * centralize the "layout glue" (padding/gaps/max widths) here so screens feel consistent.
 */
export const layout = {
  /** App page background */
  pageBg: "min-h-dvh bg-muted/40",
  /**
   * Mobile-first container matching the screenshot, with a wider desktop container.
   * This keeps mobile "full" (w-full) while improving browser use of space.
   */
  container:
    "mx-auto w-full max-w-sm px-5 py-6 md:max-w-5xl md:px-8 md:py-10",
} as const

export const spacing = {
  sectionGap: "gap-6",
  blockGap: "gap-4",
  tightGap: "gap-2",
} as const

export const radii = {
  pill: "rounded-full",
  card: "rounded-2xl",
} as const


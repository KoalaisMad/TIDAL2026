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
   * Mobile-first container with smooth breakpoints (sm → md → lg).
   * Avoids a single jump from narrow to wide; safe-area-aware padding.
   */
  container:
    "mx-auto w-full min-w-0 max-w-sm px-4 py-6 sm:max-w-xl sm:px-6 sm:py-8 md:max-w-3xl md:px-8 md:py-10 lg:max-w-5xl lg:px-10 lg:py-12",
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


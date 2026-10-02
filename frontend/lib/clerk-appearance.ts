import type { ComponentProps } from "react"
import type { ClerkProvider } from "@clerk/nextjs"

/**
 * The DESIGN.md tokens (AD-012) that Clerk's components use. Clerk derives shades from
 * these with its own colour math, which cannot read CSS variables, so the values are
 * copied from app/globals.css; tests/clerk-appearance.test.ts fails if they drift.
 */
export const CLERK_TOKENS = {
  "--accent": "#1D4E89",
  "--surface": "#FFFFFF",
  "--surface-muted": "#F1EEE7",
  "--border-input": "#D6D0C4",
  "--ink": "#16202B",
  "--ink-3": "#5A6370",
  "--positive": "#1E6B45",
  "--danger-text": "#8E1B1B",
} as const

// Clerk's sign-in and sign-up components, themed with the DESIGN.md tokens.
export const clerkAppearance: ComponentProps<typeof ClerkProvider>["appearance"] = {
  variables: {
    colorPrimary: CLERK_TOKENS["--accent"],
    colorPrimaryForeground: CLERK_TOKENS["--surface"],
    colorDanger: CLERK_TOKENS["--danger-text"],
    colorSuccess: CLERK_TOKENS["--positive"],
    colorForeground: CLERK_TOKENS["--ink"],
    colorMutedForeground: CLERK_TOKENS["--ink-3"],
    colorMuted: CLERK_TOKENS["--surface-muted"],
    colorBackground: CLERK_TOKENS["--surface"],
    colorInput: CLERK_TOKENS["--surface"],
    colorInputForeground: CLERK_TOKENS["--ink"],
    colorBorder: CLERK_TOKENS["--border-input"],
    colorRing: CLERK_TOKENS["--accent"],
    fontFamily: "var(--font-plex-sans), 'Segoe UI', system-ui, sans-serif",
    fontSize: "16px",
    borderRadius: "10px",
  },
}

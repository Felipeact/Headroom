# Spec 06: Design system in the web app

- **Milestone:** 2, foundations
- **Status:** Done
- **Depends on:** 01

## Goal

Turn `DESIGN.md` into the app's theme and shared components.

## Build

- Put the colors from `DESIGN.md` in `app/globals.css` as CSS variables, map them into Tailwind's theme, and remove the starter colors.
- Load Fraunces and IBM Plex Sans with `next/font/google`.
- Add components with the shadcn CLI, then theme them:
  `npx shadcn@latest add button card input label select switch radio-group toggle-group dialog badge skeleton sonner`
- Build a development-only page, `/dev/components`, that matches the Components mockup.

## Done when

- [x] `/dev/components` matches `design/mockups/components.dc.html`.
- [x] No hex colors appear in components, only the tokens.
- [x] The page passes an axe check in Playwright.

# Spec 01: Frontend scaffold

- **Milestone:** 1, set-up
- **Status:** Done
- **Depends on:** nothing. The repository is already set up (can run alongside 02)

## Goal

Create the Next.js app with the official generators, so none of its starting code is written by hand.

## Steps

```bash
# From the repository root, on branch development
npx create-next-app@latest frontend --yes --tailwind --eslint --app --no-src-dir --use-npm
cd frontend
npx shadcn@latest init
npm run dev        # http://localhost:3000 shows the starter page
```

- create-next-app also creates `frontend/AGENTS.md`. Keep it, and add this line at the top: "Also follow the root `AGENTS.md` and `context/DESIGN.md`."
- Commit exactly what the generators produced. Don't change any other generated file in this spec.

**Docs:** [create-next-app](https://nextjs.org/docs/app/api-reference/cli/create-next-app), [shadcn/ui for Next.js](https://ui.shadcn.com/docs/installation/next)

## Done when

- [x] `npm run dev` serves the starter page, and `npm run build` succeeds.
- [x] `components.json` exists, and no generated file was edited except `frontend/AGENTS.md`.

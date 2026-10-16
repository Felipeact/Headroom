import { api } from "./client"

// Never called: `npm run typecheck` fails if either line below stops being a type error (C10).
export async function clientTypeTest(): Promise<void> {
  // @ts-expect-error "/healthz/nope" is not a path in the schema
  await api.GET("/healthz/nope")

  const { data } = await api.GET("/healthz/live")
  if (data) {
    // @ts-expect-error LiveStatus has no "missing" field
    void data.missing
  }

  // @ts-expect-error middleware is not exposed; it would land on a throwaway client
  api.use({})
}

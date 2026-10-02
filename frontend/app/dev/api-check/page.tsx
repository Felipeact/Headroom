import { notFound } from "next/navigation"
import { api } from "@/lib/api/client"

type LiveResult = { ok: true; status: string; httpStatus: number } | { ok: false; httpStatus?: number }

async function checkLive(): Promise<LiveResult> {
  try {
    const { data, response } = await api.GET("/healthz/live")
    if (data) return { ok: true, status: data.status, httpStatus: response.status }
    return { ok: false, httpStatus: response.status }
  } catch {
    return { ok: false }
  }
}

// Development-only page that calls `GET /healthz/live` through the typed client (spec 09).
// The copy is for developers, so it is not in messages/en.json.
export default async function ApiCheckPage() {
  if (process.env.NODE_ENV === "production") notFound()
  const result = await checkLive()

  return (
    <main className="mx-auto flex w-full max-w-[1440px] flex-col gap-6 px-4 py-8 lg:px-12 lg:py-12">
      <h1 className="font-heading text-[30px] font-semibold tracking-[-0.02em] sm:text-[40px]">
        API check
      </h1>
      <div className="flex flex-col gap-1 text-sm text-ink-2">
        <p>{result.ok ? `status: ${result.status}` : "API unreachable"}</p>
        {result.httpStatus !== undefined && <p>{`HTTP ${result.httpStatus}`}</p>}
      </div>
    </main>
  )
}

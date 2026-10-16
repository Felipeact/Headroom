// A same-site path from a user-supplied value, or `fallback`. A redirect target taken from a query
// string must never leave the site (spec 32): "//host" is refused, and an absolute URL such as
// Clerk's `redirect_url` keeps only its path and query, so the origin is always this site's.
export function safePath(value: string | null | undefined, fallback = "/"): string {
  if (!value) return fallback
  if (/^https?:\/\//i.test(value)) {
    try {
      const url = new URL(value)
      return `${url.pathname}${url.search}`
    } catch {
      return fallback
    }
  }
  if (!value.startsWith("/") || value.startsWith("//") || value.startsWith("/\\")) return fallback
  return value
}

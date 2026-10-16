// Railway's health check for the web service (spec 10, AD-028). Public on purpose: it reads
// no user data and calls neither the API nor Clerk, so only this process being up decides it.
export function GET() {
  return Response.json({ status: "ok" })
}

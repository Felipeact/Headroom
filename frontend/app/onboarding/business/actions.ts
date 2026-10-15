"use server"

import * as Sentry from "@sentry/nextjs"
import { redirect } from "next/navigation"
import { authHeaders } from "@/lib/api/auth"
import { api } from "@/lib/api/client"
import { capture } from "@/lib/analytics"
import type {
  BusinessErrorKey,
  BusinessField,
  BusinessFieldErrors,
  Province,
  TimeZone,
} from "@/lib/business"

export type CreateBusinessInput = { name: string; province: Province; time_zone: TimeZone }
export type CreateBusinessResult = { fieldErrors: BusinessFieldErrors } | { formError: true }

const FIELD_ERRORS: Record<BusinessField, (type: string) => BusinessErrorKey> = {
  name: (type) => (type === "string_too_long" ? "nameTooLong" : "nameRequired"),
  province: (type) => (type === "province_not_available" ? "quebec" : "provinceRequired"),
  time_zone: () => "timeZoneRequired",
}

type FieldError = { loc: (string | number)[]; type: string }

function fieldErrors(errors: FieldError[]): BusinessFieldErrors | null {
  const result: BusinessFieldErrors = {}
  for (const error of errors) {
    const field = error.loc.at(-1)
    if (field !== "name" && field !== "province" && field !== "time_zone") return null
    result[field] ??= FIELD_ERRORS[field](error.type)
  }
  return Object.keys(result).length > 0 ? result : null
}

// Onboarding step 2 (spec 11): create the business, then go to step 3 (spec 12). A 409 means the
// user already owns one (a repeated submit, or another tab), so it lands on the dashboard.
export async function createBusiness(input: CreateBusinessInput): Promise<CreateBusinessResult> {
  let status: number
  let businessId: string | undefined
  let errors: FieldError[] = []
  try {
    const { data, error, response } = await api.POST("/v1/businesses", {
      body: { name: input.name, province: input.province, time_zone: input.time_zone },
      headers: await authHeaders(),
    })
    status = response.status
    businessId = data?.id
    if (status === 422 && error && "errors" in error) errors = error.errors
  } catch (error) {
    Sentry.captureException(error)
    return { formError: true }
  }

  if (status === 201) {
    if (businessId) await capture("business_created", { business_id: businessId })
    redirect("/onboarding/bank")
  }
  if (status === 409) redirect("/")
  if (status === 422) {
    const mapped = fieldErrors(errors)
    if (mapped) return { fieldErrors: mapped }
  }
  Sentry.captureMessage(`POST /v1/businesses returned ${status}`)
  return { formError: true }
}

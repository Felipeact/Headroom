"use server"

import * as Sentry from "@sentry/nextjs"
import { revalidatePath } from "next/cache"
import { authHeaders } from "@/lib/api/auth"
import { api } from "@/lib/api/client"
import type { components } from "@/lib/api/schema"

export type ExpectedPaymentBody = components["schemas"]["ExpectedPaymentBody"]
export type SaveResult = { ok: true } | { ok: false; status: number; detail: string | null }

const PAGE = "/expected-payments"
// The dashboard lists the next 14 days, expected payments included (spec 26 AC 25).
const DASHBOARD = "/"

// Expected payments (spec 20). Each action forwards the IDs and the values; the API checks that
// the caller owns the business, the payment and the account. On success the page re-renders
// from the API.

function failed(method: string, path: string, response: Response, error: unknown): SaveResult {
  Sentry.captureMessage(`${method} ${path} returned ${response.status}`)
  const detail =
    typeof error === "object" && error !== null && "detail" in error && typeof error.detail === "string"
      ? error.detail
      : null
  return { ok: false, status: response.status, detail }
}

function unreachable(error: unknown): SaveResult {
  Sentry.captureException(error)
  return { ok: false, status: 0, detail: null }
}

/** Add an expected payment. */
export async function createExpectedPayment(businessId: string, body: ExpectedPaymentBody): Promise<SaveResult> {
  const path = "/v1/businesses/{business_id}/expected-payments"
  try {
    const { response, error } = await api.POST(path, {
      params: { path: { business_id: businessId } },
      body,
      headers: await authHeaders(),
    })
    if (response.status !== 201) return failed("POST", path, response, error)
    revalidatePath(PAGE)
    revalidatePath(DASHBOARD)
    return { ok: true }
  } catch (error) {
    return unreachable(error)
  }
}

/** Replace an expected payment's values. */
export async function updateExpectedPayment(
  businessId: string,
  paymentId: string,
  body: ExpectedPaymentBody,
): Promise<SaveResult> {
  const path = "/v1/businesses/{business_id}/expected-payments/{payment_id}"
  try {
    const { response, error } = await api.PUT(path, {
      params: { path: { business_id: businessId, payment_id: paymentId } },
      body,
      headers: await authHeaders(),
    })
    if (response.status !== 200) return failed("PUT", path, response, error)
    revalidatePath(PAGE)
    revalidatePath(DASHBOARD)
    return { ok: true }
  } catch (error) {
    return unreachable(error)
  }
}

/** Delete an expected payment. */
export async function deleteExpectedPayment(businessId: string, paymentId: string): Promise<SaveResult> {
  const path = "/v1/businesses/{business_id}/expected-payments/{payment_id}"
  try {
    const { response, error } = await api.DELETE(path, {
      params: { path: { business_id: businessId, payment_id: paymentId } },
      headers: await authHeaders(),
    })
    if (response.status !== 204) return failed("DELETE", path, response, error)
    revalidatePath(PAGE)
    revalidatePath(DASHBOARD)
    return { ok: true }
  } catch (error) {
    return unreachable(error)
  }
}

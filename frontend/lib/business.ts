import type { components } from "@/lib/api/schema"

export type Province = components["schemas"]["BusinessCreate"]["province"]
export type TimeZone = components["schemas"]["BusinessCreate"]["time_zone"]
export type BusinessField = "name" | "province" | "time_zone"

/** Alphabetical by English name, Quebec included so choosing it can explain why not. */
export const PROVINCES: readonly Province[] = [
  "AB", "BC", "MB", "NB", "NL", "NT", "NS", "NU", "ON", "PE", "QC", "SK", "YT",
]

/** Quebec waits for French and Law 25; the API refuses it too (spec 11). */
export const UNAVAILABLE_PROVINCE: Province = "QC"

/** East to west, the eight zones the API accepts (AD-029). */
export const TIME_ZONES: readonly TimeZone[] = [
  "America/St_Johns",
  "America/Halifax",
  "America/Toronto",
  "America/Winnipeg",
  "America/Regina",
  "America/Edmonton",
  "America/Vancouver",
  "America/Whitehorse",
]

export const NAME_MAX_LENGTH = 100

/** Keys under Onboarding.Business.errors in messages/en.json. */
export type BusinessErrorKey =
  | "nameRequired"
  | "nameTooLong"
  | "provinceRequired"
  | "quebec"
  | "timeZoneRequired"

export type BusinessFieldErrors = Partial<Record<BusinessField, BusinessErrorKey>>

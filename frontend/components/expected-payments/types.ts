import type { components } from "@/lib/api/schema"

export type ExpectedPayment = components["schemas"]["ExpectedPayment"]
export type Repeats = NonNullable<ExpectedPayment["repeats"]>

/** An account counted as cash, which can hold an expected payment. */
export type AccountOption = { id: string; name: string; primary: boolean }

export const REPEATS: readonly Repeats[] = ["weekly", "biweekly", "monthly", "quarterly"]

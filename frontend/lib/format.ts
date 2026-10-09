// Money and date formatting for every screen and email. DESIGN.md, "Money" and "Dates and times".

const LOCALE = 'en-CA'
const MINUS_SIGN = '−'
const ISO_DATE = /^(\d{4})-(\d{2})-(\d{2})$/

// An ISO 4217 code. Cash is CAD only, but a bank can hold other currencies (spec 13).
type Currency = string

function wholeDollars(amountCents: number, currency: Currency, signDisplay: 'auto' | 'exceptZero') {
  if (!Number.isSafeInteger(amountCents)) {
    throw new RangeError(`amountCents must be a safe integer, got ${amountCents}`)
  }
  // Round in integer cents first: Intl would format -49 cents as "-$0".
  const dollars = Math.sign(amountCents) * Math.round(Math.abs(amountCents) / 100)
  return new Intl.NumberFormat(LOCALE, {
    style: 'currency',
    currency,
    maximumFractionDigits: 0,
    signDisplay,
  })
    .format(dollars === 0 ? 0 : dollars)
    .replace('-', MINUS_SIGN)
}

/** A balance or total in whole dollars: "$3,200", "−$3,200". */
export function formatMoney(amountCents: number, currency: Currency = 'CAD'): string {
  return wholeDollars(amountCents, currency, 'auto')
}

/** Money in or out in whole dollars, signed: "+$8,000", "−$640", "$0". */
export function formatSignedMoney(amountCents: number, currency: Currency = 'CAD'): string {
  return wholeDollars(amountCents, currency, 'exceptZero')
}

/** A plain calendar date ("YYYY-MM-DD") with the month spelled out: "Nov 9", "Fri, Oct 2". */
export function formatDate(isoDate: string, style: 'short' | 'weekday' = 'short'): string {
  const match = ISO_DATE.exec(isoDate)
  if (!match) {
    throw new RangeError(`isoDate must be YYYY-MM-DD, got "${isoDate}"`)
  }
  const [year, month, day] = match.slice(1).map(Number)
  // A plain date has no time zone, so build and format it in UTC.
  const date = new Date(Date.UTC(year, month - 1, day))
  if (date.getUTCMonth() !== month - 1 || date.getUTCDate() !== day) {
    throw new RangeError(`isoDate is not a real date: "${isoDate}"`)
  }
  return new Intl.DateTimeFormat(LOCALE, {
    timeZone: 'UTC',
    month: 'short',
    day: 'numeric',
    ...(style === 'weekday' ? { weekday: 'short' } : {}),
  }).format(date)
}

/**
 * When something happened, in the business's time zone (DESIGN.md "Dates and times"): "today at
 * 2:04 AM", or "Oct 3 at 2:04 AM" on an earlier day. `now` decides what "today" is.
 */
export function formatSyncedAt(isoDateTime: string, timeZone: string, now: Date = new Date()): string {
  const moment = new Date(isoDateTime)
  if (Number.isNaN(moment.getTime())) {
    throw new RangeError(`isoDateTime is not a date and time: "${isoDateTime}"`)
  }
  const day = new Intl.DateTimeFormat(LOCALE, { timeZone, month: 'short', day: 'numeric' })
  // en-CA writes "2:04 a.m."; DESIGN.md writes "6:02 AM".
  const time = new Intl.DateTimeFormat('en-US', { timeZone, hour: 'numeric', minute: '2-digit' }).format(moment)
  const ymd = new Intl.DateTimeFormat('en-CA', { timeZone, year: 'numeric', month: '2-digit', day: '2-digit' })
  const today = ymd.format(moment) === ymd.format(now)
  return `${today ? 'today' : day.format(moment)} at ${time}`
}

// The largest amount an expected payment can hold: $99,999,999.99 (spec 20, AC 5).
export const MAX_AMOUNT_CENTS = 9_999_999_999
const AMOUNT_INPUT = /^\d+(\.\d{1,2})?$/

/** An amount for an input field, unsigned with cents: "8,000.00", "2,300.50". */
export function formatAmountInput(amountCents: number): string {
  if (!Number.isSafeInteger(amountCents)) {
    throw new RangeError(`amountCents must be a safe integer, got ${amountCents}`)
  }
  return new Intl.NumberFormat(LOCALE, { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(
    Math.abs(amountCents) / 100,
  )
}

/**
 * What someone typed as an amount, in whole cents, or null when it isn't one: digits with an
 * optional "$", thousands commas and up to 2 decimals. "2,300.50" is 230050.
 */
export function parseAmountInput(text: string): number | null {
  const plain = text.trim().replace(/^\$/, '').replaceAll(',', '').trim()
  if (!AMOUNT_INPUT.test(plain)) return null
  const [dollars, cents = ''] = plain.split('.')
  const total = Number(dollars) * 100 + Number(cents.padEnd(2, '0'))
  return Number.isSafeInteger(total) ? total : null
}

// The largest minimum balance: $10,000,000 (spec 23, AD-088).
export const MAX_MINIMUM_CENTS = 1_000_000_000
const WHOLE_DOLLARS_INPUT = /^\d+$/

/** Whole dollars for an input field, unsigned with thousands commas: "5,000". */
export function formatWholeDollarsInput(amountCents: number): string {
  if (!Number.isSafeInteger(amountCents)) {
    throw new RangeError(`amountCents must be a safe integer, got ${amountCents}`)
  }
  return new Intl.NumberFormat(LOCALE, { maximumFractionDigits: 0 }).format(Math.round(Math.abs(amountCents) / 100))
}

/**
 * A typed minimum balance in cents, or null when it isn't whole dollars from $0 to $10,000,000:
 * digits with an optional "$" and thousands commas. "$5,000" is 500000.
 */
export function parseWholeDollars(text: string): number | null {
  const plain = text.trim().replace(/^\$/, '').replaceAll(',', '').trim()
  if (!WHOLE_DOLLARS_INPUT.test(plain)) return null
  const cents = Number(plain) * 100
  return Number.isSafeInteger(cents) && cents <= MAX_MINIMUM_CENTS ? cents : null
}

/** Names joined as a sentence: "A", "A and B", "A, B, and C". */
export function formatList(items: string[]): string {
  return new Intl.ListFormat('en', { style: 'long', type: 'conjunction' }).format(items)
}

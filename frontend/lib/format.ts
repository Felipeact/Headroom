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

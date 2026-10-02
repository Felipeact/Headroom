import { afterEach, describe, expect, test } from 'vitest'
import { formatDate, formatMoney, formatSignedMoney } from './format'

const MINUS = '−'

describe('formatMoney', () => {
  test('C27 money whole dollars', () => {
    expect(formatMoney(320000)).toBe('$3,200')
    expect(formatMoney(-320000)).toBe(`${MINUS}$3,200`)
    expect(formatMoney(-320000).codePointAt(0)).toBe(0x2212)
  })

  test('C28 money grouping', () => {
    expect(formatMoney(4230000)).toBe('$42,300')
    expect(formatMoney(0)).toBe('$0')
  })

  test('C29 money rounding', () => {
    expect(formatMoney(320050)).toBe('$3,201')
    expect(formatMoney(-320050)).toBe(`${MINUS}$3,201`)
    expect(formatMoney(320049)).toBe('$3,200')
  })

  test('C30 zero has no sign', () => {
    expect(formatMoney(-49)).toBe('$0')
    expect(formatMoney(49)).toBe('$0')
    expect(formatSignedMoney(-49)).toBe('$0')
    expect(formatSignedMoney(49)).toBe('$0')
    expect(formatSignedMoney(0)).toBe('$0')
  })

  test('C31 signed money', () => {
    expect(formatSignedMoney(800000)).toBe('+$8,000')
    expect(formatSignedMoney(-64000)).toBe(`${MINUS}$640`)
  })

  test('C32 rejects non-integer cents', () => {
    for (const bad of [3200.5, Number.NaN, Number.POSITIVE_INFINITY, 2 ** 53]) {
      expect(() => formatMoney(bad)).toThrow(RangeError)
      expect(() => formatSignedMoney(bad)).toThrow(RangeError)
    }
  })
})

describe('formatDate', () => {
  const originalTz = process.env.TZ

  afterEach(() => {
    process.env.TZ = originalTz
  })

  test('C34 date styles', () => {
    expect(formatDate('2026-11-09')).toBe('Nov 9')
    expect(formatDate('2026-10-02', 'weekday')).toBe('Fri, Oct 2')
  })

  test('C35 date ignores time zone', () => {
    process.env.TZ = 'America/Vancouver'
    expect(formatDate('2026-10-02')).toBe('Oct 2')
    process.env.TZ = 'Pacific/Auckland'
    expect(formatDate('2026-10-02')).toBe('Oct 2')
  })

  test('C36 rejects malformed dates', () => {
    for (const bad of ['2026-02-30', '10/02/2026', '', '2026-10-2']) {
      expect(() => formatDate(bad)).toThrow(RangeError)
    }
  })
})

test('C33 no hyphen minus', () => {
  const outputs = [-320050, -320000, -64000, -49, 0, 49, 320000].flatMap((cents) => [
    formatMoney(cents),
    formatSignedMoney(cents),
  ])
  for (const date of ['2026-01-01', '2026-10-02', '2026-12-31']) {
    outputs.push(formatDate(date), formatDate(date, 'weekday'))
  }
  for (const output of outputs) {
    expect(output).not.toContain('-')
  }
})

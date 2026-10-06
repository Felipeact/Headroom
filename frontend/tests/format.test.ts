import { afterEach, beforeEach, describe, expect, test, vi } from 'vitest'
import { formatSyncedAt } from '@/lib/format'

const TORONTO = 'America/Toronto'

beforeEach(() => {
  vi.useFakeTimers({ toFake: ['Date'] })
  vi.setSystemTime(new Date('2026-10-06T14:00:00Z')) // 10:00 in Toronto
})

afterEach(() => {
  vi.useRealTimers()
})

describe('format', () => {
  test.each([
    ['2026-10-06T06:04:00Z', 'today at 2:04 AM'],
    ['2026-10-03T06:04:00Z', 'Oct 3 at 2:04 AM'],
    // 23:30 on Oct 5 in Toronto, though already Oct 6 in UTC.
    ['2026-10-06T03:30:00Z', 'Oct 5 at 11:30 PM'],
  ])('C8 synced time %s', (iso, expected) => {
    expect(formatSyncedAt(iso, TORONTO)).toBe(expected)
  })
})

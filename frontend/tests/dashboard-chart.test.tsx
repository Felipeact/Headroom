import { render, screen } from '@testing-library/react'
import { createTranslator, NextIntlClientProvider } from 'next-intl'
import { cloneElement, type ComponentProps, type ReactElement } from 'react'
import { afterEach, beforeEach, describe, expect, test, vi } from 'vitest'
import { chartSummary } from '@/components/dashboard/chart-summary'
import { chartPoints, ForecastChart, xTicks } from '@/components/dashboard/forecast-chart'
import type { Dashboard } from '@/components/dashboard/types'
import messages from '@/messages/en.json'
import { sampleDashboard, WEEK_ENDS } from './fixtures/dashboard-sample'

// The props each series was drawn with, to read `isAnimationActive` (C38).
const drawn = vi.hoisted(() => ({ Line: [] as Record<string, unknown>[], Area: [] as Record<string, unknown>[] }))
vi.mock('recharts', async (importOriginal) => {
  const actual = await importOriginal<typeof import('recharts')>()
  return {
    ...actual,
    // jsdom has no layout, so the responsive container would measure 0 and draw nothing.
    ResponsiveContainer: ({ children }: { children: ReactElement<{ width?: number; height?: number }> }) =>
      cloneElement(children, { width: 800, height: 280 }),
    Line: (props: ComponentProps<typeof actual.Line>) => {
      drawn.Line.push(props as unknown as Record<string, unknown>)
      return <actual.Line {...props} />
    },
    Area: (props: ComponentProps<typeof actual.Area>) => {
      drawn.Area.push(props as unknown as Record<string, unknown>)
      return <actual.Area {...props} />
    },
  }
})

class NoResizeObserver {
  observe() {}
  unobserve() {}
  disconnect() {}
}

function media({ desktop, reduced }: { desktop: boolean; reduced: boolean }) {
  window.matchMedia = ((query: string) => ({
    matches: query.includes('min-width: 1024px') ? desktop : query.includes('reduce') ? reduced : false,
    media: query,
    addEventListener: () => {},
    removeEventListener: () => {},
  })) as unknown as typeof window.matchMedia
}

beforeEach(() => {
  vi.stubGlobal('ResizeObserver', NoResizeObserver)
  drawn.Line.length = 0
  drawn.Area.length = 0
})

afterEach(() => {
  vi.unstubAllGlobals()
})

type Forecast = NonNullable<Dashboard['forecast']>
const forecast = sampleDashboard().forecast as Forecast

function renderChart(minimumCents: number | null) {
  return render(
    <NextIntlClientProvider locale="en" messages={messages}>
      <ForecastChart forecast={forecast} minimumCents={minimumCents} currency="CAD" />
    </NextIntlClientProvider>,
  )
}

function svgTexts(container: HTMLElement): string[] {
  return Array.from(container.querySelectorAll('svg text')).map((t) => (t.textContent ?? '').trim())
}

function legend(container: HTMLElement, viewport: 'desktop' | 'phone'): string[] {
  const hidden = viewport === 'desktop' ? 'lg:hidden' : 'max-lg:hidden'
  return Array.from(container.querySelectorAll('ul > li')).map((li) =>
    Array.from(li.querySelectorAll('span'))
      .filter((span) => !span.classList.contains(hidden))
      .map((span) => span.textContent)
      .join('') + Array.from(li.childNodes).filter((n) => n.nodeType === Node.TEXT_NODE).map((n) => n.textContent).join(''),
  )
}

describe('the forecast chart', () => {
  test('points labels legend', () => {
    const points = chartPoints(forecast, 'Today')
    expect(points).toHaveLength(14)
    expect(points[0]).toMatchObject({ label: 'Today', cents: 4230000, balance: 42300 })
    forecast.weeks.forEach((week, i) => {
      expect(points[i + 1].cents).toBe(week.end_balance_cents)
      expect(points[i + 1].range).toEqual([week.low_cents / 100, week.high_cents / 100])
    })
    expect(points[7].label).toBe('Nov 9')
    expect(xTicks(points, true)).toEqual(['Today', 'Sep 28', 'Oct 12', 'Oct 26', 'Nov 9', 'Nov 23', 'Dec 7', 'Dec 21'])
    expect(xTicks(points, false)).toEqual(['Today', 'Oct 12', 'Nov 9', 'Dec 7'])

    media({ desktop: true, reduced: false })
    let view = renderChart(500000)
    let texts = svgTexts(view.container)
    for (const tick of ['Today', 'Sep 28', 'Oct 12', 'Oct 26', 'Nov 9', 'Nov 23', 'Dec 7', 'Dec 21']) expect(texts).toContain(tick)
    expect(texts).toContain('Your $5,000 minimum')
    expect(texts).toContain('Low $3,150')
    expect(legend(view.container, 'desktop')).toEqual(['Projected balance', 'Likely range', 'Your $5,000 minimum'])
    view.unmount()

    media({ desktop: false, reduced: false })
    view = renderChart(500000)
    texts = svgTexts(view.container)
    for (const tick of ['Today', 'Oct 12', 'Nov 9', 'Dec 7']) expect(texts).toContain(tick)
    expect(texts).not.toContain('Sep 28')
    expect(texts).toContain('Min $5,000')
    expect(legend(view.container, 'phone')).toEqual(['Projected balance', 'Likely range', 'Your minimum'])
    view.unmount()

    media({ desktop: true, reduced: false })
    view = renderChart(null)
    texts = svgTexts(view.container)
    expect(texts.some((t) => t.includes('minimum') || t.startsWith('Min'))).toBe(false)
    expect(legend(view.container, 'desktop')).toEqual(['Projected balance', 'Likely range'])
  })

  test('text summary', () => {
    const t = createTranslator({ locale: 'en', messages, namespace: 'Dashboard.chart' })
    const last = `$${(WEEK_ENDS[12] / 100).toLocaleString('en-CA')}`
    expect(chartSummary(t, forecast, 500000, 'CAD')).toBe(
      `Your cash is projected to go from $42,300 today to ${last} by the week of Dec 21. ` +
        'The lowest point is $3,150 in the week of Nov 9, $1,850 below your $5,000 minimum.',
    )
    expect(chartSummary(t, forecast, 300000, 'CAD')).toBe(
      `Your cash is projected to go from $42,300 today to ${last} by the week of Dec 21. ` +
        'The lowest point is $3,150 in the week of Nov 9, above your $3,000 minimum.',
    )
    expect(chartSummary(t, forecast, null, 'CAD')).toBe(
      `Your cash is projected to go from $42,300 today to ${last} by the week of Dec 21. ` +
        'The lowest point is $3,150 in the week of Nov 9.',
    )
    expect(screen.queryByRole('img')).toBeNull()
  })

  test('reduced motion', () => {
    media({ desktop: true, reduced: true })
    let view = renderChart(500000)
    expect(drawn.Line.at(-1)?.isAnimationActive).toBe(false)
    expect(drawn.Area.at(-1)?.isAnimationActive).toBe(false)
    view.unmount()

    media({ desktop: true, reduced: false })
    view = renderChart(500000)
    expect(drawn.Line.at(-1)?.isAnimationActive).toBe(true)
    expect(drawn.Area.at(-1)?.isAnimationActive).toBe(true)
  })
})

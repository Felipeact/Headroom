import type { Dashboard } from '@/components/dashboard/types'

// The sample (seed 0) as the API returns it on 2026-09-26 with the $5,000 minimum: the values
// spec 26 C1-C4 prove against the real API. Week ends other than Nov 9 are illustrative.
export const IDS = {
  harbor: 'conn-harbor',
  summit: 'conn-summit',
  operating: 'acc-operating',
  reserve: 'acc-reserve',
  visa: 'acc-visa',
  line: 'acc-line',
  alert: 'alert-1',
}

const MONDAYS = [
  '2026-09-28', '2026-10-05', '2026-10-12', '2026-10-19', '2026-10-26', '2026-11-02', '2026-11-09',
  '2026-11-16', '2026-11-23', '2026-11-30', '2026-12-07', '2026-12-14', '2026-12-21',
]
const SUNDAYS = [
  '2026-10-04', '2026-10-11', '2026-10-18', '2026-10-25', '2026-11-01', '2026-11-08', '2026-11-15',
  '2026-11-22', '2026-11-29', '2026-12-06', '2026-12-13', '2026-12-20', '2026-12-27',
]
export const WEEK_ENDS = [
  3080000, 3260000, 2410000, 2550000, 2200000, 1765000, 315000, 1980000, 2120000, 2050000, 2300000, 2240000,
  2516000,
]

const account = (overrides: Partial<Dashboard['accounts'][number]>): Dashboard['accounts'][number] => ({
  id: 'acc',
  connection_id: IDS.harbor,
  institution_name: 'Harbor Community Bank',
  name: 'Account',
  type: 'checking',
  mask: null,
  currency: 'CAD',
  balance_cents: 0,
  available_cents: null,
  included: false,
  primary: false,
  next_payment_on: null,
  ...overrides,
})

type Alert = Dashboard['alerts'][number]
type AlertItem = Alert['items'][number]
type Fix = Alert['fixes'][number]

export const COASTAL: AlertItem = {
  kind: 'cause',
  date: '2026-11-12',
  amount_cents: -1450000,
  currency: 'CAD',
  description: 'Coastal Supply Co, quarterly order',
  counterparty: null,
  source: 'expected_payment',
  schedule: null,
}
export const PAYROLL: AlertItem = {
  kind: 'cause',
  date: '2026-11-13',
  amount_cents: -1120000,
  currency: 'CAD',
  description: 'Payroll',
  counterparty: 'Payroll',
  source: 'recurring_pattern',
  schedule: 'biweekly',
}
const BIRCH: AlertItem = {
  kind: 'arrives_after',
  date: '2026-11-17',
  amount_cents: 960000,
  currency: 'CAD',
  description: 'Birch & Co, invoice 1057',
  counterparty: null,
  source: 'expected_payment',
  schedule: null,
}

const fix = (overrides: Partial<Fix>): Fix => ({
  kind: 'pay_early',
  amount_cents: 0,
  currency: 'CAD',
  original_date: null,
  repay_on: null,
  date: '2026-11-10',
  description: null,
  counterparty: null,
  available_cents: null,
  new_lowest_balance_cents: 0,
  ...overrides,
})

export const FIXES: Record<Fix['kind'], Fix> = {
  pay_early: fix({
    kind: 'pay_early',
    amount_cents: 960000,
    original_date: '2026-11-17',
    date: '2026-11-10',
    description: 'Birch & Co, invoice 1057',
    new_lowest_balance_cents: 1275000,
  }),
  move_payment: fix({
    kind: 'move_payment',
    amount_cents: -1450000,
    original_date: '2026-11-12',
    date: '2026-11-19',
    description: 'Coastal Supply Co, quarterly order',
    new_lowest_balance_cents: 1765000,
  }),
  draw_credit: fix({
    kind: 'draw_credit',
    amount_cents: 200000,
    date: '2026-11-09',
    repay_on: '2026-11-17',
    description: 'Line of credit',
    available_cents: 2000000,
    new_lowest_balance_cents: 515000,
  }),
  financing: fix({
    kind: 'financing',
    amount_cents: 200000,
    date: '2026-11-09',
    repay_on: '2026-11-16',
    new_lowest_balance_cents: 515000,
  }),
}

export const ALERT: Alert = {
  id: IDS.alert,
  state: 'open',
  starts_on: '2026-11-09',
  ends_on: '2026-11-15',
  lowest_week_starts_on: '2026-11-09',
  lowest_balance_cents: 315000,
  minimum_cents: 500000,
  shortfall_cents: 185000,
  currency: 'CAD',
  created_at: '2026-09-26T10:05:00Z',
  updated_at: '2026-09-26T10:05:00Z',
  dismissed_at: null,
  resolved_at: null,
  items: [COASTAL, PAYROLL, BIRCH],
  fixes: [FIXES.pay_early, FIXES.move_payment, FIXES.draw_credit],
}

const item = (overrides: Partial<Dashboard['upcoming'][number]>): Dashboard['upcoming'][number] => ({
  id: 'item',
  date: '2026-10-02',
  account_id: IDS.operating,
  amount_cents: 0,
  currency: 'CAD',
  source: 'recurring_pattern',
  source_id: null,
  description: null,
  counterparty: null,
  schedule: null,
  ...overrides,
})

export const UPCOMING: Dashboard['upcoming'] = [
  item({ id: 'u1', date: '2026-10-02', amount_cents: -1120000, description: 'Payroll', counterparty: 'Payroll', schedule: 'biweekly' }),
  item({ id: 'u2', date: '2026-10-06', amount_cents: 800000, source: 'expected_payment', description: 'Acme Co, invoice 1042' }),
  item({
    id: 'u3',
    date: '2026-10-07',
    amount_cents: -64000,
    description: 'Software subscriptions',
    counterparty: 'Fieldworks Software',
    schedule: 'monthly',
  }),
  item({ id: 'u4', date: '2026-10-08', amount_cents: -245000, source: 'card_payment', source_id: IDS.visa, description: 'Business Visa' }),
]

export function sampleDashboard(overrides: Partial<Dashboard> = {}): Dashboard {
  return {
    as_of: '2026-09-26',
    currency: 'CAD',
    cash_on_hand_cents: 4230000,
    available_credit_cents: 2000000,
    minimum_balance_cents: 500000,
    projected_low: { week_starts_on: '2026-11-09', balance_cents: 315000 },
    next_card_payment: { account_id: IDS.visa, date: '2026-10-08', amount_cents: -245000 },
    accounts: [
      account({
        id: IDS.operating,
        name: 'Operating checking',
        mask: '2381',
        balance_cents: 800000,
        included: true,
        primary: true,
      }),
      account({ id: IDS.reserve, name: 'Reserve savings', type: 'savings', mask: '9025', balance_cents: 3430000, included: true }),
      account({ id: IDS.line, name: 'Line of credit', type: 'line_of_credit', mask: '7702', balance_cents: 0, available_cents: 2000000 }),
      account({
        id: IDS.visa,
        connection_id: IDS.summit,
        institution_name: 'Summit Federal',
        name: 'Business Visa',
        type: 'credit_card',
        mask: '5530',
        balance_cents: 245000,
        next_payment_on: '2026-10-08',
      }),
    ],
    connections: [
      { id: IDS.harbor, institution_name: 'Harbor Community Bank', status: 'synced', last_synced_at: '2026-09-26T10:02:00Z' },
      { id: IDS.summit, institution_name: 'Summit Federal', status: 'synced', last_synced_at: '2026-09-26T10:02:00Z' },
    ],
    forecast: {
      id: 'snap-1',
      computed_at: '2026-09-26T10:03:00Z',
      opening_balance_cents: 4230000,
      incomplete: false,
      weeks: MONDAYS.map((starts_on, i) => ({
        number: i + 1,
        starts_on,
        ends_on: SUNDAYS[i],
        end_balance_cents: WEEK_ENDS[i],
        low_cents: WEEK_ENDS[i] - 150000,
        high_cents: WEEK_ENDS[i] + 150000,
      })),
    },
    alerts: [ALERT],
    upcoming: UPCOMING,
    ...overrides,
  }
}

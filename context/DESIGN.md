# DESIGN.md

The design system and writing guidelines for Headroom's web app and emails. Every spec that touches the web app or emails builds against this file and the mockups in `design/mockups/`.

Like the contracts, this file is shared. Change it only in its own commit, and only after asking.

The live mockups are on the Headroom mockups canvas. `design/mockups/` holds a copy of every artboard's source, which shows the exact layout, sizes, and colors. To add pictures of the screens to the repository, export them from the canvas.

## Principles

1. **Calm, not alarming.** Owners open Headroom when money is tight. Warnings are clear and specific, never loud.
2. **Specific beats general.** Always name the payment, the amount, and the date.
3. **One job per screen.** Each screen has one main action.
4. **Answer "Am I OK?" in two seconds.** The dashboard answers that question at a glance.
5. **Earn trust at the moment it matters.** Say what Headroom can and can't do with bank data, right where people decide.

## Colors

Define these as CSS variables in `app/globals.css`, and map them in the Tailwind config. Never put a hex value directly in a component.

| Token | Hex | Use |
|---|---|---|
| `--bg` | `#F5F3EE` | Page background |
| `--surface` | `#FFFFFF` | Cards, dialogs, and inputs |
| `--surface-muted` | `#F1EEE7` | Segmented controls and subtle fills |
| `--surface-active` | `#E9E5DC` | The current navigation item |
| `--border` | `#E2DDD3` | Card and divider borders |
| `--border-input` | `#D6D0C4` | Input borders |
| `--ink` | `#16202B` | Main text |
| `--ink-2` | `#454F5C` | Secondary text |
| `--ink-3` | `#5A6370` | Captions and chart labels |
| `--accent` | `#1D4E89` | Primary buttons, links, focus rings, and the forecast line |
| `--accent-hover` | `#133A68` | Hover and pressed states |
| `--positive` | `#1E6B45` | Money in, "synced", and "no shortfall" |
| `--positive-bg` | `#EAF4EE` | The "new lowest balance" result on a fix |
| `--warning-bg`, `--warning-border` | `#FFF4E2`, `#F0D3A4` | Cash gaps and the projected low |
| `--warning-text`, `--warning-strong` | `#7A4300`, `#4F2C00` | Text on warning backgrounds |
| `--warning-line` | `#B26B00` | The minimum-balance line on charts |
| `--danger-bg`, `--danger-border` | `#FCEDEB`, `#EFC7C2` | Account shortfalls, errors, and destructive actions |
| `--danger-text`, `--danger-strong` | `#8E1B1B`, `#5E1111` | Text on danger backgrounds, and error messages |
| `--line-soft` | `#ECE8E0` | Skeleton blocks and chart gridlines |
| `--line-strong` | `#C9C2B5` | A switch that is off, and the chart's zero line |

Rules:

- **Contrast:** text meets WCAG AA, which is 4.5:1 for body text and 3:1 for text 24px and larger. Every text pairing above passes.
- **Never color alone:** warnings and errors always have an icon and words too.
- **Money signs:** money going out is shown in `--ink` with a minus sign, never in red. Only money in gets a color, `--positive`, with a plus sign.

## Typography

| Role | Font, size, weight | Use |
|---|---|---|
| Display | Fraunces, 40 (30 on phones), 600 | Page titles |
| Figure | Fraunces, 36 (26–40 on phones), 600 | Big numbers on summary cards |
| Title | IBM Plex Sans, 19 (17 on phones), 600 | Alert and dialog titles |
| Section | IBM Plex Sans, 18 (17 on phones), 600 | Card and section headings |
| Body | IBM Plex Sans, 15, 400 | Everything else |
| Secondary | IBM Plex Sans, 14, 400–500 | Descriptions and labels |
| Caption | IBM Plex Sans, 13, 400 | Hints and metadata |
| Eyebrow | IBM Plex Sans, 12, 600, uppercase, 0.06em letter spacing | Alert types such as "Cash gap", and group labels |

- **Fallbacks:** Fraunces falls back to Georgia, then serif. IBM Plex Sans falls back to Segoe UI, then system-ui, then sans-serif.
- **Loading:** load both fonts with `next/font/google`.
- **Numbers:** always use `font-variant-numeric: tabular-nums`, so amounts line up in columns.
- **Inputs:** use 16px text in inputs, so phones don't zoom in when a field is tapped.
- **Casing:** use sentence case everywhere, including titles, buttons, and labels.

## Spacing, shape, and layout

- **Spacing scale (px):** 4, 8, 12, 16, 20, 24, 32, 48. Use Tailwind's matching steps.
- **Corner radius:**
  - 14px for cards
  - 12px for cards inside cards and for large buttons
  - 10px for buttons and inputs
  - 6px for badges
- **Shadows:** none, except on dialogs and on the selected option in a segmented control. Borders and the background color do the separating.
- **Page layout:** content is at most 1344px wide. Pages have 48px of side padding on desktop and 16–20px on phones.
- **Breakpoints:** use Tailwind's defaults. Design for phones first; the dashboard switches to two columns at `lg` (1024px).
- **Touch targets:** at least 44 by 44 pixels, including icon buttons and switches.

## Icons

- Use `lucide-react`, with a 1.8px stroke, at 16–24px.
- An icon next to text is decorative, so mark it `aria-hidden`. An icon-only button needs an `aria-label`.

## Components

All shared components live in `frontend/components/ui/`. They're shadcn/ui components, themed with the tokens above. Build every screen from them, and don't create look-alikes. The Components page of the canvas shows each one.

| Component | Rules |
|---|---|
| Button | Five variants: primary (accent fill), secondary (white with a border), outline (white with an ink border, for the main action inside an alert), text link, and destructive (danger text). All are at least 44px tall, with 10px corners and 15px semibold text. A screen has at most one primary button. |
| Card | White, with a 1px border, 14px corners, and 20–24px padding (16–18px on phones). |
| Summary card | A label, a big figure, and a caption. It switches to the warning style when the value is below the minimum. |
| Alert card | Warning style for a cash gap, danger style for an account shortfall. It contains an eyebrow with an icon, a title, a one-paragraph cause, a white "fix" box, and the actions. |
| Badge | A small label (Primary, Recurring, Expected) or a status (Synced, Needs attention, Overdraws). |
| Input and select | The label sits above, the field is 48px tall, and hints sit below. An error shows danger text under the field and a 2px danger border, linked with `aria-describedby`. |
| Money input | A `$` inside the field. It accepts "5000" and "5,000", and stores cents. |
| Switch | Used for "Counts as cash". Always has a visible label. |
| Segmented control | Used for small either-or choices, such as "Money out" or "Money in", and for the chart's account picker. |
| Dialog | On desktop, centered and 480px wide. On phones, a full-screen sheet. It has a title, then the fields, then Cancel and the primary action, right-aligned. |
| Step indicator | "Step 2 of 5" plus a five-segment bar. Used only in onboarding. |
| Skeleton | Gray blocks in the shape of the content, shown while loading. |
| Toast | Confirms a change, such as "Expected payment added", for 4 seconds. Never used for an error that needs action. |
| Forecast chart | Recharts, with these styles: <ul><li>the line in `--accent`, 2.5px wide</li><li>the likely range in accent at 13% opacity</li><li>gridlines in `--line-soft` and the zero line in `--line-strong`</li><li>the minimum as a dashed `--warning-line`</li><li>the lowest point labeled</li></ul>It always comes with a text summary for screen readers. |

## States

Every screen and every data card has these states:

- **Loading:** skeletons shaped like the content. Never show a spinner on its own for more than a second.
- **Empty:** an icon, a one-line title that says what's missing, one sentence on why it matters, and one action. For example: the title "No bank connected yet", the sentence "Connect your bank to see your 13-week forecast.", and the button "Connect your bank".
- **Error:** what happened, in plain words, and what to do next. For example: "We couldn't load your forecast. Check your connection and try again.", with the button "Try again". Never make an error code the main text.
- **Partial:** when some data is missing, for example because a bank needs attention, show what's there. Add a warning banner that names the bank and offers "Reconnect".

## Writing

**Voice:** a calm, experienced bookkeeper. Plain, specific, and kind. Never alarmist, and never cute.

- **Name the thing.** "A $14,500 supplier payment and $11,200 of payroll land in the same week" beats "Large outflows detected."
- **Lead with the answer.** Titles state the situation: "Cash falls below your $5,000 minimum the week of Nov 9."
- **Say what to do next.** Every alert and every error ends with an action.
- **Start buttons with a verb** that says what happens: "Connect your bank", "Add expected payment", "Review transfer". Never "Submit" or "OK".
- **Use everyday words.** Say "money in", "money out", "cash gap", and "minimum balance". Avoid "liquidity", "burn", "outflows", and "delta".
- **Use Canadian English,** such as "cheque" and "centre", and familiar payment terms such as "e-Transfer".
- **Name Headroom when talking about data access.** Say "Headroom can't move money", not "we can't move money". In other messages, "we" is fine: "We couldn't load your forecast."

**Money**

- Use whole dollars in summaries and alerts: "$42,300". Show cents only in transaction lists, and only when they aren't zero.
- Use a true minus sign for negative amounts ("−$3,200") and a plus sign for money in ("+$8,000").
- Write just "$" in v1, since everything is in Canadian dollars. Once other currencies arrive, write "CA$" and "US$".

**Dates and times**

- Always spell out the month: "Fri, Oct 2" and "Nov 9". Canadians write numeric dates both day-first and month-first, so "10/02" is ambiguous.
- Refer to a forecast week by its Monday: "the week of Nov 9".
- Show times in the business's time zone: "Updated today at 6:02 AM".

**Trust copy.** Use this on the bank connection screen and in settings:

> Headroom can see your balances and transactions. It can't move money, and it never sees your bank password. You can disconnect at any time.

## Emails

- **Layout:** 600px wide and one column, with the Headroom wordmark at the top.
- **Fonts:** headings in Georgia and body text in the system sans-serif, because web fonts don't load reliably in email.
- **Buttons:** one button per email, in `--accent`.
- **Plain text:** every email has a plain-text version.
- **Footer:** every email ends with:
  - why the person is receiving it
  - links to email preferences and to unsubscribe
  - Headroom's mailing address

  Canada's anti-spam law (CASL) requires the mailing address and an unsubscribe link in commercial messages. The simplest approach is to include them in every email.
- **All clear:** when there are no gaps, the digest still arrives, with the numbers and a short "all clear" message, so owners know Headroom is working.

## Accessibility

- **Standard:** aim for WCAG 2.2 AA.
- **Keyboard:** everything works with the keyboard alone, and focus is always visible, as a 2px `--accent` outline offset by 2px.
- **Real elements:** use real buttons, links, and form labels. Never make a `div` clickable.
- **Charts:** always include a text summary.
- **Motion:** respect the "reduce motion" setting by turning off animated transitions for those users.
- **Testing:** every spec that adds a screen includes an automated axe check in its Playwright tests.

## Mockups

| Screen | Canvas page | File in `design/mockups/` | Spec |
|---|---|---|---|
| Dashboard, desktop and phone | Dashboard | `dashboard-desktop.dc.html`, `dashboard-phone.dc.html` | 26 |
| Onboarding: business details, connecting a bank, choosing accounts, minimum balance, and building the forecast | Onboarding | `onboarding-*.dc.html` | 11, 12, 13, 23 |
| Settings: bank connections (desktop) | Other screens | `settings-banks.dc.html` | 17 |
| Alert page (phone) | Other screens | `alert.dc.html` | 27 |
| Expected payments, with the add dialog open (desktop) | Other screens | `expected-payments.dc.html` | 20 |
| Alert email and weekly digest | Emails | `email-alert.dc.html`, `email-digest.dc.html` | 29, 30 |
| Components and states | Components | `components.dc.html` | 06 |

- **Sign-up and sign-in:** these use Clerk's components, themed with these tokens through Clerk's appearance settings, so they have no mockup of their own.
- **Onboarding on desktop:** onboarding is designed for phones. On desktop, the same column is centered, at most 480px wide.
- **Settings on phones:** settings are designed for desktop. On phones, the list of sections becomes its own screen.
- **Screens without a mockup,** such as the other settings sections, follow the closest mockup and this file.
- **Parts marked "later":** the mockups show the full vision. Parts that the specs mark "later", such as the account-shortfall alert on the dashboard, aren't built in v1.

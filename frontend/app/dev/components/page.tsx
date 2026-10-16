import { auth } from "@clerk/nextjs/server"
import { notFound } from "next/navigation"
import { CircleAlert, Landmark, TriangleAlert } from "lucide-react"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { Skeleton } from "@/components/ui/skeleton"
import { Switch } from "@/components/ui/switch"
import { DialogAndToastDemo } from "./dialog-and-toast-demo"
import { SegmentedControlDemo } from "./segmented-control-demo"
import { TokenSwatch } from "./token-swatch"

// Development-only reference page for design/mockups/components.dc.html. The copy is the
// mockup's, so it is not in messages/en.json.

const SWATCHES = [
  { name: "Background", token: "bg", className: "border border-border bg-bg" },
  { name: "Surface", token: "surface", className: "border border-border bg-surface" },
  { name: "Surface muted", token: "surface-muted", className: "border border-border bg-surface-muted" },
  { name: "Border", token: "border", className: "bg-border" },
  { name: "Ink", token: "ink", className: "bg-ink" },
  { name: "Ink 2", token: "ink-2", className: "bg-ink-2" },
  { name: "Ink 3", token: "ink-3", className: "bg-ink-3" },
  { name: "Accent", token: "accent", className: "bg-accent" },
  { name: "Positive", token: "positive", className: "bg-positive" },
  { name: "Warning background", token: "warning-bg", className: "border border-warning-border bg-warning-bg" },
  { name: "Warning text", token: "warning-text", className: "bg-warning-text" },
  { name: "Warning line", token: "warning-line", className: "bg-warning-line" },
  { name: "Danger background", token: "danger-bg", className: "border border-danger-border bg-danger-bg" },
  { name: "Danger text", token: "danger-text", className: "bg-danger-text" },
]

const TYPE_SCALE = [
  { label: "Display · Fraunces 40 / 600", sample: "Cash flow", className: "font-heading text-[30px] font-semibold tracking-[-0.02em] sm:text-[40px]" },
  { label: "Figure · Fraunces 36 / 600", sample: "$42,300", className: "font-heading text-[26px] font-semibold tracking-[-0.02em] sm:text-[36px]" },
  { label: "Title · Plex Sans 19 / 600", sample: "Cash falls below your $5,000 minimum the week of Nov 9", className: "text-[17px] font-semibold sm:text-[19px]" },
  { label: "Section · Plex Sans 18 / 600", sample: "13-week forecast", className: "text-[17px] font-semibold sm:text-lg" },
  { label: "Body · Plex Sans 15 / 400", sample: "Payroll of $11,200 leaves Operating checking on Friday, Oct 2.", className: "text-[15px]" },
  { label: "Caption · Plex Sans 13 / 400", sample: "Updated today at 6:02 AM", className: "text-[13px] text-ink-3" },
  { label: "Eyebrow · Plex Sans 12 / 600", sample: "Cash gap", className: "text-xs font-semibold tracking-[0.06em] text-warning-text uppercase" },
]

const EYEBROW = "text-xs font-semibold tracking-[0.06em] uppercase"

function Section({ id, title, children }: { id: string; title: string; children: React.ReactNode }) {
  return (
    <section aria-labelledby={id} className="flex flex-col gap-4">
      <h2 id={id} className="text-xl font-semibold">
        {title}
      </h2>
      {children}
    </section>
  )
}

export default async function DevComponentsPage() {
  if (process.env.NODE_ENV === "production") notFound()
  await auth.protect()

  return (
    <main className="mx-auto flex w-full max-w-[1440px] flex-col gap-10 px-4 py-8 lg:px-12 lg:py-12">
      <div className="flex flex-col gap-1.5">
        <h1 className="font-heading text-[30px] font-semibold tracking-[-0.02em] sm:text-[40px]">
          Components and states
        </h1>
        <p className="text-[15px] text-ink-2">
          Build every screen from these. The tokens and rules are in DESIGN.md.
        </p>
      </div>

      <Section id="c-colors" title="Colors">
        <ul className="grid grid-cols-1 gap-x-4 gap-y-5 sm:grid-cols-4 lg:grid-cols-7">
          {SWATCHES.map((swatch) => (
            <TokenSwatch key={swatch.token} {...swatch} />
          ))}
        </ul>
      </Section>

      <Section id="c-type" title="Type">
        <Card className="py-2">
          <ul className="flex flex-col px-(--card-spacing)">
            {TYPE_SCALE.map((row) => (
              <li
                key={row.label}
                className="flex flex-col gap-1 border-b border-surface-muted py-3.5 last:border-b-0 sm:flex-row sm:items-baseline sm:gap-6"
              >
                <div className="text-[13px] text-ink-3 sm:w-[220px] sm:shrink-0">{row.label}</div>
                <div className={row.className}>{row.sample}</div>
              </li>
            ))}
          </ul>
        </Card>
      </Section>

      <Section id="c-buttons" title="Buttons">
        <div className="flex flex-wrap items-center gap-3">
          <Button>Primary: Add expected payment</Button>
          <Button variant="secondary">Secondary: Dismiss</Button>
          <Button variant="outline">Outline: See all fixes</Button>
          <Button variant="link" asChild>
            <a href="#c-buttons">Text link: Manage</a>
          </Button>
          <Button variant="destructive">Destructive: Disconnect</Button>
          <Button aria-disabled="true">Disabled: Continue</Button>
        </div>
      </Section>

      <Section id="c-forms" title="Form controls">
        <Card>
          <CardContent className="grid grid-cols-1 gap-6 lg:grid-cols-3">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="f-name">Business name</Label>
              <Input id="f-name" defaultValue="Harbor Street Plumbing" />
              <div className="text-[13px] text-ink-3">Hint text sits under the field.</div>
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="f-amount">Amount</Label>
              <div className="relative">
                <span
                  aria-hidden="true"
                  className="absolute top-1/2 left-3.5 -translate-y-1/2 text-base font-semibold text-ink-2"
                >
                  $
                </span>
                <Input
                  id="f-amount"
                  defaultValue="0"
                  inputMode="decimal"
                  aria-invalid="true"
                  aria-describedby="f-amount-error"
                  className="pl-7"
                />
              </div>
              <div id="f-amount-error" className="flex items-center gap-1.5 text-[13px] text-danger-text">
                <CircleAlert className="size-3.5" strokeWidth={2.2} />
                Enter an amount greater than $0.
              </div>
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="f-province">Province or territory</Label>
              <Select defaultValue="ON">
                <SelectTrigger id="f-province">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="AB">Alberta</SelectItem>
                  <SelectItem value="BC">British Columbia</SelectItem>
                  <SelectItem value="NS">Nova Scotia</SelectItem>
                  <SelectItem value="ON">Ontario</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="flex flex-col gap-1">
              <div className="text-sm font-semibold">Switch</div>
              <div className="flex min-h-11 items-center justify-between">
                <span className="text-sm">Counts as cash (on)</span>
                <Switch defaultChecked aria-label="Counts as cash" />
              </div>
              <div className="flex min-h-11 items-center justify-between">
                <span className="text-sm">Counts as cash (off)</span>
                <Switch aria-label="Counts as cash" />
              </div>
            </div>
            <div className="flex flex-col gap-1">
              <div id="f-radio" className="text-sm font-semibold">
                Radio
              </div>
              <RadioGroup defaultValue="primary" aria-labelledby="f-radio" className="gap-0">
                <Label className="min-h-11 text-sm font-normal" htmlFor="f-primary">
                  <RadioGroupItem id="f-primary" value="primary" />
                  Primary account
                </Label>
                <Label className="min-h-11 text-sm font-normal" htmlFor="f-make-primary">
                  <RadioGroupItem id="f-make-primary" value="make-primary" />
                  Make primary
                </Label>
              </RadioGroup>
            </div>
            <div className="flex flex-col gap-1.5">
              <div className="text-sm font-semibold">Segmented control</div>
              <SegmentedControlDemo />
            </div>
          </CardContent>
        </Card>
      </Section>

      <Section id="c-badges" title="Badges">
        <div className="flex flex-wrap items-center gap-3">
          <Badge variant="neutral">Primary</Badge>
          <Badge variant="muted">Recurring</Badge>
          <Badge variant="muted">Expected</Badge>
          <Badge variant="positive">Synced</Badge>
          <Badge variant="warning">Needs attention</Badge>
          <Badge variant="danger">Overdraws Operating</Badge>
        </div>
      </Section>

      <Section id="c-alerts" title="Alert cards">
        <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">
          <article className="flex flex-col gap-2 rounded-[14px] border border-warning-border bg-warning-bg px-[22px] py-5">
            <div className={`${EYEBROW} text-warning-text`}>Cash gap · warning</div>
            <div className="text-[17px] font-semibold text-warning-strong">
              Cash falls below your $5,000 minimum the week of Nov 9
            </div>
            <div className="text-sm leading-normal text-warning-strong">
              Used when the combined balance is forecast to drop below the minimum.
            </div>
          </article>
          <article className="flex flex-col gap-2 rounded-[14px] border border-danger-border bg-danger-bg px-[22px] py-5">
            <div className={`${EYEBROW} text-danger-text`}>Account shortfall · danger (later)</div>
            <div className="text-[17px] font-semibold text-danger-strong">
              Operating checking will be overdrawn on Friday, Oct 2
            </div>
            <div className="text-sm leading-normal text-danger-strong">
              Used when one account runs short while the total is fine.
            </div>
          </article>
        </div>
      </Section>

      <Section id="c-states" title="States">
        <div className="grid grid-cols-1 gap-5 lg:grid-cols-3">
          <Card>
            <CardContent className="flex flex-col gap-3">
              <div className={`${EYEBROW} text-ink-3`}>Loading</div>
              <Skeleton aria-hidden="true" className="h-3.5 w-2/5 rounded-[6px]" />
              <Skeleton aria-hidden="true" className="h-8 w-[70%] rounded-[8px]" />
              <Skeleton aria-hidden="true" className="h-3 w-[55%] rounded-[6px]" />
              <Skeleton aria-hidden="true" className="h-[90px] w-full rounded-[10px] bg-surface-muted" />
            </CardContent>
          </Card>
          <Card>
            <CardContent className="flex flex-col items-start gap-3">
              <div className={`${EYEBROW} text-ink-3`}>Empty</div>
              <Landmark className="size-7 text-ink-2" strokeWidth={1.6} />
              <div className="text-[17px] font-semibold">No bank connected yet</div>
              <div className="text-sm leading-normal text-ink-2">
                Connect your bank to see your 13-week forecast.
              </div>
              <Button>Connect your bank</Button>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="flex flex-col items-start gap-3">
              <div className={`${EYEBROW} text-ink-3`}>Error</div>
              <CircleAlert className="size-7 text-danger-text" strokeWidth={1.6} />
              <div className="text-[17px] font-semibold">We couldn&apos;t load your forecast</div>
              <div className="text-sm leading-normal text-ink-2">Check your connection and try again.</div>
              <Button variant="secondary">Try again</Button>
            </CardContent>
          </Card>
        </div>
        <div
          data-testid="partial-banner"
          className="flex flex-col gap-3 rounded-xl border border-warning-border bg-warning-bg px-4 py-3 sm:flex-row sm:items-center sm:justify-between sm:gap-4"
        >
          <div className="flex items-center gap-2.5 text-sm text-warning-strong">
            <TriangleAlert className="size-5 shrink-0 text-warning-text" strokeWidth={1.8} />
            <span>
              <strong className="font-semibold">Partial:</strong> Summit Federal needs attention, so your
              forecast is missing its latest data.
            </span>
          </div>
          <Button variant="outline" className="shrink-0 text-sm">
            Reconnect
          </Button>
        </div>
      </Section>

      <Section id="c-overlays" title="Dialog and toast">
        <DialogAndToastDemo />
      </Section>
    </main>
  )
}

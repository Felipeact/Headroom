import { useTranslations } from "next-intl"
import { cn } from "cn"

// DESIGN.md "Step indicator": "Step 2 of 5" plus a five-segment bar, used only in onboarding
// (AD-034). `children` (the wordmark) sits at the start of the row, the step text at the end,
// as in the onboarding mockups. The text says it all, so the bar is hidden from screen readers.
export function StepIndicator({
  step,
  total,
  children,
}: {
  step: number
  total: number
  children?: React.ReactNode
}) {
  const t = useTranslations("Onboarding")

  return (
    <div className="flex flex-col gap-3">
      <div className="flex min-h-11 items-center justify-between gap-3">
        {children}
        <p className="text-[13px] text-ink-2">{t("stepOf", { step, total })}</p>
      </div>
      <div
        data-testid="step-bar"
        aria-hidden="true"
        className="grid gap-1"
        style={{ gridTemplateColumns: `repeat(${total}, minmax(0, 1fr))` }}
      >
        {Array.from({ length: total }, (_, index) => (
          <div
            key={index}
            className={cn("h-1 rounded-sm", index < step ? "bg-accent" : "bg-border")}
          />
        ))}
      </div>
    </div>
  )
}

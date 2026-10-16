import { TriangleAlert } from "lucide-react"
import { cn } from "cn"

// One summary card (AC 12): a label, an amount, and a note. `warning` marks a low below the minimum.
export function SummaryCard({
  label,
  amount,
  note,
  warning = false,
  className,
}: {
  label: string
  amount: string
  note: React.ReactNode
  warning?: boolean
  className?: string
}) {
  return (
    <section
      aria-label={label}
      data-testid="summary-card"
      className={cn(
        "flex flex-col gap-2 rounded-[14px] border px-[22px] py-5",
        warning ? "border-warning-border bg-warning-bg" : "border-border bg-surface",
        className,
      )}
    >
      <h2 className={cn("flex items-center gap-1.5 text-sm font-medium", warning ? "text-warning-text" : "text-ink-2")}>
        {warning && <TriangleAlert aria-hidden="true" className="size-4 shrink-0" strokeWidth={2} />}
        {label}
      </h2>
      <p
        className={cn(
          "font-heading text-[30px] font-semibold tracking-[-0.02em] tabular-nums lg:text-[36px]",
          warning && "text-warning-strong",
        )}
      >
        {amount}
      </p>
      <p className={cn("text-[13px]", warning ? "text-warning-text" : "text-ink-3")}>{note}</p>
    </section>
  )
}

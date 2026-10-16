import * as React from "react"
import { cva, type VariantProps } from "class-variance-authority"
import { cn } from "cn"
import { Slot } from "radix-ui"

const badgeVariants = cva(
  "group/badge inline-flex w-fit shrink-0 items-center justify-center gap-1 overflow-hidden rounded-[6px] border border-transparent px-2 py-[3px] text-xs font-medium whitespace-nowrap [&>svg]:pointer-events-none [&>svg]:size-3!",
  {
    variants: {
      variant: {
        neutral:
          "border-border bg-surface text-[11px] font-semibold tracking-[0.04em] text-ink-2 uppercase",
        muted: "bg-surface-muted text-ink-2",
        positive: "bg-positive-bg text-positive",
        warning: "bg-warning-bg text-warning-text",
        danger: "bg-danger-text font-semibold text-surface",
      },
    },
    defaultVariants: {
      variant: "muted",
    },
  }
)

function Badge({
  className,
  variant = "muted",
  asChild = false,
  ...props
}: React.ComponentProps<"span"> &
  VariantProps<typeof badgeVariants> & { asChild?: boolean }) {
  const Comp = asChild ? Slot.Root : "span"

  return (
    <Comp
      data-slot="badge"
      data-variant={variant}
      className={cn(badgeVariants({ variant }), className)}
      {...props}
    />
  )
}

export { Badge, badgeVariants }

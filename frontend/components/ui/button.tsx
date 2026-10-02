import * as React from "react"
import { cva, type VariantProps } from "class-variance-authority"
import { cn } from "cn"
import { Slot } from "radix-ui"

const buttonVariants = cva(
  "group/button inline-flex shrink-0 items-center justify-center gap-2 rounded-[10px] border text-[15px] whitespace-nowrap transition-colors select-none disabled:cursor-not-allowed disabled:border-transparent disabled:bg-surface-active disabled:text-ink-3 aria-disabled:cursor-not-allowed aria-disabled:border-transparent aria-disabled:bg-surface-active aria-disabled:text-ink-3 [&_svg]:pointer-events-none [&_svg]:shrink-0 [&_svg:not([class*='size-'])]:size-5",
  {
    variants: {
      variant: {
        primary:
          "border-transparent bg-accent font-semibold text-surface hover:bg-accent-hover",
        secondary:
          "border-border-input bg-surface font-medium text-ink hover:bg-surface-muted",
        outline:
          "border-ink bg-surface font-semibold text-ink hover:bg-surface-muted",
        link: "border-transparent font-medium text-accent underline underline-offset-4 hover:text-accent-hover",
        destructive:
          "border-danger-border bg-surface font-medium text-danger-text hover:bg-danger-bg",
        ghost:
          "border-transparent bg-transparent font-medium text-ink hover:bg-surface-muted",
      },
      size: {
        default: "min-h-11 px-[18px]",
        icon: "size-11",
      },
    },
    compoundVariants: [{ variant: "link", size: "default", className: "px-1.5" }],
    defaultVariants: {
      variant: "primary",
      size: "default",
    },
  }
)

function Button({
  className,
  variant = "primary",
  size = "default",
  asChild = false,
  ...props
}: React.ComponentProps<"button"> &
  VariantProps<typeof buttonVariants> & {
    asChild?: boolean
  }) {
  const Comp = asChild ? Slot.Root : "button"

  return (
    <Comp
      data-slot="button"
      data-variant={variant}
      data-size={size}
      className={cn(buttonVariants({ variant, size, className }))}
      {...props}
    />
  )
}

export { Button, buttonVariants }

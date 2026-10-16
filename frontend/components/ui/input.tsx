import * as React from "react"
import { cn } from "cn"

function Input({ className, type, ...props }: React.ComponentProps<"input">) {
  return (
    <input
      type={type}
      data-slot="input"
      className={cn(
        "h-12 w-full min-w-0 rounded-[10px] border border-border-input bg-surface px-3.5 text-base text-ink transition-colors file:inline-flex file:h-6 file:border-0 file:bg-transparent file:text-sm file:font-medium file:text-ink placeholder:text-ink-3 disabled:cursor-not-allowed disabled:bg-surface-muted disabled:text-ink-3 aria-invalid:border-2 aria-invalid:border-danger-text",
        className
      )}
      {...props}
    />
  )
}

export { Input }

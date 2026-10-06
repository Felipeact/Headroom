import { CircleAlert } from "lucide-react"

// The message under a field the dialog can't send yet.
export function FieldError({ id, message }: { id: string; message: string }) {
  return (
    <p id={id} className="flex items-start gap-1.5 text-[13px] text-danger-text">
      <CircleAlert aria-hidden="true" className="mt-px size-4 shrink-0" strokeWidth={1.8} />
      <span>{message}</span>
    </p>
  )
}

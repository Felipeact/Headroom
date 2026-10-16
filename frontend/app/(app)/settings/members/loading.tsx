import { useTranslations } from "next-intl"
import { Skeleton } from "@/components/ui/skeleton"

export default function Loading() {
  const t = useTranslations("States")

  return (
    <div role="status" aria-busy="true" aria-label={t("loading")} className="flex flex-col gap-5">
      <Skeleton className="h-7 w-40" />
      <Skeleton className="h-4 w-full max-w-md" />
      <Skeleton className="h-12 w-full rounded-[10px]" />
      <Skeleton className="h-32 w-full rounded-[14px]" />
    </div>
  )
}

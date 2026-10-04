import { useTranslations } from "next-intl"
import { Skeleton } from "@/components/ui/skeleton"

export default function Loading() {
  const t = useTranslations("States")

  return (
    <div aria-busy="true" aria-label={t("loading")} className="flex flex-col gap-6">
      <Skeleton className="h-11 w-full" />
      <Skeleton className="h-16 w-3/4" />
      <Skeleton className="h-12 w-full" />
      <Skeleton className="h-12 w-full" />
      <Skeleton className="h-12 w-full" />
    </div>
  )
}

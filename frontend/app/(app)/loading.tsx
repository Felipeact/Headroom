import { useTranslations } from "next-intl"
import { Skeleton } from "@/components/ui/skeleton"

export default function Loading() {
  const t = useTranslations("States")

  return (
    <div aria-busy="true" aria-label={t("loading")} className="flex flex-col gap-4">
      <Skeleton className="h-10 w-48 sm:w-64" />
      <Skeleton className="h-4 w-full max-w-md" />
      <Skeleton className="h-40 w-full rounded-[14px]" />
    </div>
  )
}

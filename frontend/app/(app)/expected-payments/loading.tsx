import { useTranslations } from "next-intl"
import { Skeleton } from "@/components/ui/skeleton"

export default function Loading() {
  const t = useTranslations("States")

  return (
    <div role="status" aria-busy="true" aria-label={t("loading")} className="flex flex-col gap-5">
      <Skeleton className="h-10 w-72" />
      <Skeleton className="h-4 w-full max-w-md" />
      <Skeleton className="h-72 w-full rounded-[14px]" />
    </div>
  )
}

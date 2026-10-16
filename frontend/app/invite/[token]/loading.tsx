import { useTranslations } from "next-intl"
import { Skeleton } from "@/components/ui/skeleton"

export default function Loading() {
  const t = useTranslations("States")

  return (
    <main className="mx-auto flex w-full max-w-[480px] flex-1 flex-col gap-6 px-5 pt-6 pb-7">
      <div role="status" aria-busy="true" aria-label={t("loading")} className="flex flex-col gap-4">
        <Skeleton className="h-7 w-48" />
        <Skeleton className="h-8 w-full" />
        <Skeleton className="h-4 w-full" />
        <Skeleton className="h-12 w-40 rounded-[10px]" />
      </div>
    </main>
  )
}

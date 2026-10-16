import { useTranslations } from "next-intl"
import { Skeleton } from "@/components/ui/skeleton"

// The dashboard while its data loads (AC 26): blocks in the shape of the cards, chart and panels.
export function DashboardSkeleton() {
  const t = useTranslations("States")

  return (
    <div aria-busy="true" aria-label={t("loading")} className="flex flex-col gap-5 lg:gap-6">
      <Skeleton className="h-10 w-48 sm:w-64" />
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4 lg:gap-5">
        {[0, 1, 2, 3].map((n) => (
          <Skeleton key={n} data-testid="skeleton-card" className="h-[120px] rounded-[14px]" />
        ))}
      </div>
      <div className="flex flex-col gap-5 lg:flex-row lg:gap-6">
        <Skeleton data-testid="skeleton-chart" className="h-[340px] rounded-[14px] lg:flex-[2]" />
        <Skeleton data-testid="skeleton-panel" className="h-[340px] rounded-[14px] lg:flex-1" />
      </div>
      <Skeleton data-testid="skeleton-panel" className="h-[240px] rounded-[14px]" />
    </div>
  )
}

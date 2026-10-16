import Link from "next/link"
import { SearchX } from "lucide-react"
import { useTranslations } from "next-intl"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"

// An unknown, foreign or malformed alert id (spec 27 AC 21).
export default function AlertNotFound() {
  const t = useTranslations("AlertPage")

  return (
    <Card className="mx-auto w-full max-w-[640px]">
      <CardContent className="flex flex-col items-start gap-3">
        <SearchX aria-hidden="true" className="size-7 text-ink-3" strokeWidth={1.6} />
        <h1 className="text-[17px] font-semibold sm:text-[19px]">{t("notFoundTitle")}</h1>
        <p className="text-sm leading-normal text-ink-2">{t("notFoundBody")}</p>
        <Button asChild variant="secondary">
          <Link href="/">{t("notFoundAction")}</Link>
        </Button>
      </CardContent>
    </Card>
  )
}

import Link from "next/link"
import type { LucideIcon } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"

// An empty state (DESIGN.md "States"): an icon, a title, one sentence, and one action.
export function NoticeCard({
  icon: Icon,
  title,
  body,
  action,
  href,
  headingLevel = 2,
}: {
  icon: LucideIcon
  title: string
  body: string
  action: string
  href: string
  headingLevel?: 1 | 2
}) {
  const Heading = headingLevel === 1 ? "h1" : "h2"
  return (
    <Card>
      <CardContent className="flex flex-col items-start gap-3">
        <Icon aria-hidden="true" className="size-7 text-ink-2" strokeWidth={1.6} />
        <Heading className="text-[17px] font-semibold sm:text-[19px]">{title}</Heading>
        <p className="text-sm leading-normal text-ink-2">{body}</p>
        <Button asChild>
          <Link href={href}>{action}</Link>
        </Button>
      </CardContent>
    </Card>
  )
}

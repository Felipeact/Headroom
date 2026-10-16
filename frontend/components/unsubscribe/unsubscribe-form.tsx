"use client"

import Link from "next/link"
import { type ReactNode, useState, useTransition } from "react"
import { useTranslations } from "next-intl"
import { type UnsubscribeResult, unsubscribe } from "@/app/unsubscribe/[token]/actions"
import { Button } from "@/components/ui/button"

const PREFERENCES = "/settings/email"

function preferencesLink(chunks: ReactNode) {
  return (
    <Link href={PREFERENCES} className="font-semibold text-accent underline underline-offset-2">
      {chunks}
    </Link>
  )
}

export function UnsubscribeForm({ token }: { token: string }) {
  const t = useTranslations("Unsubscribe")
  const [result, setResult] = useState<UnsubscribeResult["status"] | null>(null)
  const [pending, startTransition] = useTransition()

  if (result === "unsubscribed" || result === "invalid") {
    const done = result === "unsubscribed"
    return (
      <div className="flex flex-col gap-3">
        <h1 className="font-heading text-[26px] font-semibold leading-tight">
          {t(done ? "doneTitle" : "invalidTitle")}
        </h1>
        <p className="text-[15px] leading-normal text-ink-2">
          {t.rich(done ? "doneBody" : "invalidBody", { link: preferencesLink })}
        </p>
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-4">
      <h1 className="font-heading text-[26px] font-semibold leading-tight">{t("title")}</h1>
      <p className="text-[15px] leading-normal text-ink-2">{t("body")}</p>
      <Button
        className="w-full sm:w-auto"
        disabled={pending}
        onClick={() =>
          startTransition(async () => {
            setResult((await unsubscribe(token)).status)
          })
        }
      >
        {pending ? t("pending") : t("button")}
      </Button>
      {result === "error" && (
        <p role="alert" className="text-sm text-danger-text">
          {t("failed")}
        </p>
      )}
    </div>
  )
}

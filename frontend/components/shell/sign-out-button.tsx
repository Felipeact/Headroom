"use client"

import { SignOutButton as ClerkSignOutButton } from "@clerk/nextjs"
import { useTranslations } from "next-intl"
import { Button } from "@/components/ui/button"

export function SignOutButton({ className }: { className?: string }) {
  const t = useTranslations("Shell")

  return (
    <ClerkSignOutButton redirectUrl="/sign-in">
      <Button variant="ghost" className={className}>
        {t("signOut")}
      </Button>
    </ClerkSignOutButton>
  )
}

"use client"

import { useState } from "react"
import { MenuIcon, XIcon } from "lucide-react"
import { useTranslations } from "next-intl"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog"
import { NavLinks } from "./nav-links"
import { SignOutButton } from "./sign-out-button"

export function MobileMenu({ className, userName }: { className?: string; userName?: string }) {
  const t = useTranslations("Shell")
  const [open, setOpen] = useState(false)

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button variant="secondary" size="icon" aria-label={t("openMenu")} className={className}>
          <MenuIcon aria-hidden="true" />
        </Button>
      </DialogTrigger>
      <DialogContent showCloseButton={false} aria-describedby={undefined}>
        <DialogTitle>{t("menuTitle")}</DialogTitle>
        <nav aria-label={t("mainNav")}>
          <NavLinks className="flex-col" onNavigate={() => setOpen(false)} />
        </nav>
        {userName && (
          <div
            data-testid="menu-user"
            className="flex flex-col items-start gap-1 border-t border-border pt-3"
          >
            <span data-user-content className="px-3.5 text-[15px] text-ink-2">{userName}</span>
            <SignOutButton />
          </div>
        )}
        <DialogClose asChild>
          <Button
            variant="ghost"
            size="icon"
            aria-label={t("closeMenu")}
            className="absolute top-2 right-2"
          >
            <XIcon aria-hidden="true" />
          </Button>
        </DialogClose>
      </DialogContent>
    </Dialog>
  )
}

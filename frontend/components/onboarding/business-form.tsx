"use client"

import { useRef, useState, useSyncExternalStore, useTransition } from "react"
import { CircleAlert } from "lucide-react"
import { useTranslations } from "next-intl"
import { createBusiness } from "@/app/onboarding/business/actions"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import {
  NAME_MAX_LENGTH,
  PROVINCES,
  TIME_ZONES,
  UNAVAILABLE_PROVINCE,
  type BusinessErrorKey,
  type BusinessField,
  type BusinessFieldErrors,
  type Province,
  type TimeZone,
} from "@/lib/business"

const FIELD_ORDER: BusinessField[] = ["name", "province", "time_zone"]

function deviceTimeZone(): TimeZone | "" {
  const zone = Intl.DateTimeFormat().resolvedOptions().timeZone
  return TIME_ZONES.find((candidate) => candidate === zone) ?? ""
}

// The device's zone never changes while the page is open, so there is nothing to subscribe to.
const subscribeNever = () => () => {}

function validate(name: string, province: string, timeZone: string): BusinessFieldErrors {
  const errors: BusinessFieldErrors = {}
  const trimmed = name.trim()
  if (!trimmed) errors.name = "nameRequired"
  else if (trimmed.length > NAME_MAX_LENGTH) errors.name = "nameTooLong"
  if (!province) errors.province = "provinceRequired"
  else if (province === UNAVAILABLE_PROVINCE) errors.province = "quebec"
  if (!timeZone) errors.time_zone = "timeZoneRequired"
  return errors
}

function FieldError({ id, message }: { id: string; message: string }) {
  return (
    <p id={id} className="flex items-start gap-1.5 text-[13px] text-danger-text">
      <CircleAlert aria-hidden="true" className="mt-px size-4 shrink-0" strokeWidth={1.8} />
      <span>{message}</span>
    </p>
  )
}

// Onboarding step 2, from design/mockups/onboarding-2-business.dc.html (spec 11).
export function BusinessForm() {
  const t = useTranslations("Onboarding")
  const [name, setName] = useState("")
  const [province, setProvince] = useState<Province | "">("")
  const [chosenTimeZone, setTimeZone] = useState<TimeZone | "">("")
  // Read in the browser only: the server cannot know the device's zone.
  const fromDevice = useSyncExternalStore(subscribeNever, deviceTimeZone, () => "" as const)
  const timeZone = chosenTimeZone || fromDevice
  const [errors, setErrors] = useState<BusinessFieldErrors>({})
  const [formError, setFormError] = useState(false)
  const [pending, startTransition] = useTransition()
  const nameRef = useRef<HTMLInputElement>(null)
  const provinceRef = useRef<HTMLButtonElement>(null)
  const timeZoneRef = useRef<HTMLButtonElement>(null)

  // Quebec is explained as soon as it is chosen, not only after Continue.
  const shown: BusinessFieldErrors = {
    ...errors,
    ...(province === UNAVAILABLE_PROVINCE ? { province: "quebec" as const } : {}),
  }
  const message = (key: BusinessErrorKey) => t(`Business.errors.${key}`)
  const describedBy = (field: BusinessField, hintId: string) =>
    [hintId, shown[field] ? `${field}-error` : null].filter(Boolean).join(" ")

  function focusFirst(found: BusinessFieldErrors) {
    const first = FIELD_ORDER.find((field) => found[field])
    const refs = { name: nameRef, province: provinceRef, time_zone: timeZoneRef }
    if (first) refs[first].current?.focus()
  }

  function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (pending) return
    const found = validate(name, province, timeZone)
    setErrors(found)
    setFormError(false)
    if (Object.keys(found).length > 0 || !province || !timeZone) {
      focusFirst(found)
      return
    }
    startTransition(async () => {
      const result = await createBusiness({ name: name.trim(), province, time_zone: timeZone })
      if ("fieldErrors" in result) {
        setErrors(result.fieldErrors)
        focusFirst(result.fieldErrors)
      } else {
        setFormError(true)
      }
    })
  }

  return (
    <form noValidate onSubmit={submit} className="flex flex-1 flex-col gap-6">
      <div className="flex flex-col gap-5">
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="business-name">{t("Business.nameLabel")}</Label>
          <Input
            ref={nameRef}
            id="business-name"
            name="name"
            autoComplete="organization"
            value={name}
            onChange={(event) => setName(event.target.value)}
            aria-invalid={shown.name ? true : undefined}
            aria-describedby={shown.name ? "name-error" : undefined}
          />
          {shown.name && <FieldError id="name-error" message={message(shown.name)} />}
        </div>

        <div className="flex flex-col gap-1.5">
          <Label htmlFor="province">{t("Business.provinceLabel")}</Label>
          <Select value={province} onValueChange={(value) => setProvince(value as Province)}>
            <SelectTrigger
              ref={provinceRef}
              id="province"
              aria-invalid={shown.province ? true : undefined}
              aria-describedby={describedBy("province", "province-hint")}
            >
              <SelectValue placeholder={t("Business.provincePlaceholder")} />
            </SelectTrigger>
            <SelectContent>
              {PROVINCES.map((code) => (
                <SelectItem key={code} value={code}>
                  {t(`provinces.${code}`)}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <p id="province-hint" className="text-[13px] text-ink-3">
            {t("Business.quebecHint")}
          </p>
          {shown.province && (
            <FieldError id="province-error" message={message(shown.province)} />
          )}
        </div>

        <div className="flex flex-col gap-1.5">
          <Label htmlFor="time-zone">{t("Business.timeZoneLabel")}</Label>
          <Select value={timeZone} onValueChange={(value) => setTimeZone(value as TimeZone)}>
            <SelectTrigger
              ref={timeZoneRef}
              id="time-zone"
              aria-invalid={shown.time_zone ? true : undefined}
              aria-describedby={describedBy("time_zone", "time-zone-hint")}
            >
              <SelectValue placeholder={t("Business.timeZonePlaceholder")} />
            </SelectTrigger>
            <SelectContent>
              {TIME_ZONES.map((zone) => (
                <SelectItem key={zone} value={zone}>
                  {t(`timeZones.${zone}`)}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <p id="time-zone-hint" className="text-[13px] text-ink-3">
            {t("Business.timeZoneHint")}
          </p>
          {shown.time_zone && (
            <FieldError id="time_zone-error" message={message(shown.time_zone)} />
          )}
        </div>
      </div>

      <div className="mt-auto flex flex-col gap-3">
        {formError && (
          <p role="alert" className="flex items-start gap-1.5 text-sm text-danger-text">
            <CircleAlert aria-hidden="true" className="mt-px size-4 shrink-0" strokeWidth={1.8} />
            <span>{t("Business.errors.saveFailed")}</span>
          </p>
        )}
        <Button type="submit" disabled={pending} aria-busy={pending} className="min-h-[52px] text-base">
          {t("Business.continue")}
        </Button>
      </div>
    </form>
  )
}


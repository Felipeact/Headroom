"use client"

import { useSyncExternalStore } from "react"

function subscribe() {
  return () => {}
}

// The CSS compiler shortens six-digit hex values to three digits where it can; show the
// six-digit, uppercase form DESIGN.md uses.
function fullHex(value: string): string {
  const short = /^#([0-9a-f])([0-9a-f])([0-9a-f])$/i.exec(value)
  const hex = short ? `#${short[1]}${short[1]}${short[2]}${short[2]}${short[3]}${short[3]}` : value
  return hex.toUpperCase()
}

// The caption reads the value from the CSS variable itself, so globals.css stays the only
// place a hex value is written.
export function TokenSwatch({
  name,
  token,
  className,
}: {
  name: string
  token: string
  className: string
}) {
  const value = useSyncExternalStore(
    subscribe,
    () =>
      fullHex(
        getComputedStyle(document.documentElement).getPropertyValue(`--${token}`).trim()
      ),
    () => ""
  )

  return (
    <li className="flex flex-col gap-1.5">
      <div aria-hidden="true" className={`h-16 rounded-[10px] ${className}`} />
      <div className="text-sm font-semibold">{name}</div>
      <div className="text-[13px] text-ink-3">
        {value ? `--${token} · ${value}` : `--${token}`}
      </div>
    </li>
  )
}

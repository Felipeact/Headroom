"use client"

import { useState } from "react"
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group"

export function SegmentedControlDemo() {
  const [direction, setDirection] = useState("out")

  return (
    <ToggleGroup
      type="single"
      aria-label="Direction"
      spacing={1}
      value={direction}
      // A segmented control always has one choice, so ignore the click that would clear it.
      onValueChange={(value) => value && setDirection(value)}
      className="grid w-full grid-cols-2"
    >
      <ToggleGroupItem value="out">Money out</ToggleGroupItem>
      <ToggleGroupItem value="in">Money in</ToggleGroupItem>
    </ToggleGroup>
  )
}

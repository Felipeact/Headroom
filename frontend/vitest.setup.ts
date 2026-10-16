import { afterEach } from 'vitest'
import { cleanup } from '@testing-library/react'

// Testing Library cleans up on its own only when `afterEach` is a global, and Vitest globals are off.
afterEach(() => {
  cleanup()
})

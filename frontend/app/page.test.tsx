import { expect, test } from 'vitest'
import { render, screen } from '@testing-library/react'
import Page from './page'

test('Page renders its main heading', () => {
  render(<Page />)
  expect(screen.getByRole('heading', { level: 1 })).toBeDefined()
})

test('each test starts from an empty document', () => {
  render(<Page />)
  expect(screen.getAllByRole('heading', { level: 1 })).toHaveLength(1)
})

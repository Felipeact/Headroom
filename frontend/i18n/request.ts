import { getRequestConfig } from 'next-intl/server'
import messages from '../messages/en.json'

// v1 is English only, so the locale is fixed and URLs carry no locale segment (plan door 3).
export default getRequestConfig(async () => ({
  locale: 'en',
  messages,
}))

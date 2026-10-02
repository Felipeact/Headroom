import messages from './messages/en.json'

// Type-checks every message key against messages/en.json.
declare module 'next-intl' {
  interface AppConfig {
    Messages: typeof messages
  }
}

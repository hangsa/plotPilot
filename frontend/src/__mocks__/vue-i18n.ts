// Stub for `vue-i18n`. The app does not actually install vue-i18n,
// but a few components import { useI18n } from 'vue-i18n' and call t()
// in templates. This stub returns the key string (identity function) so
// rendering and tests work without pulling in the real package.

export function useI18n() {
  return {
    t: (key: string) => key,
    d: (key: string | number | Date) => String(key),
    n: (key: number) => String(key),
    locale: { value: 'en' },
  }
}

export const i18n = {
  global: {
    t: (key: string) => key,
  },
}

export default { useI18n, i18n }
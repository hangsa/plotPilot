import { defineConfig } from 'vitest/config'
import vue from '@vitejs/plugin-vue'
import { resolve } from 'path'

// Stub for `vue-i18n`: app does not install vue-i18n, but some components
// import it for type-tolerance. In tests, map it to an identity stub module
// so SFC compilation succeeds.
const i18nStubPath = resolve(__dirname, 'src/__mocks__/vue-i18n.ts')

// Stub for StoryOS view components that are not yet implemented (owned by
// later tasks E1/F*). Routing tests import the router module which lazy-loads
// these views; alias each missing path to a tiny placeholder so vite's
// import-analysis step does not error before mocks apply.
//
// Aliases must be declared in specificity order (most specific first), since
// vite resolves aliases in array order and a less-specific `@` prefix would
// otherwise pre-empt the per-path matches below.
const stubSfcPath = resolve(__dirname, 'src/__mocks__/stub-component.vue')

export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: [
      { find: 'vue-i18n', replacement: i18nStubPath },
      // Lazy-imported StoryOS views — alias to a placeholder SFC.
      { find: '@/views/workbench/storyos/PredeclaredDiff.vue', replacement: stubSfcPath },
      // Generic `@/...` alias LAST so the per-path matches above take priority.
      { find: '@', replacement: resolve(__dirname, 'src') },
    ],
  },
  test: {
    environment: 'jsdom',
    setupFiles: [resolve(__dirname, 'src/__mocks__/resize-observer.ts')],
  },
})
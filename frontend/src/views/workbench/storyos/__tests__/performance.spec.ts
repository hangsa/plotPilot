import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import { setActivePinia, createPinia } from 'pinia'
import CascadeGraph from '../CascadeGraph.vue'

// Scope note (E6, 1D): this smoke-test measures empty-state mount latency.
// True "100 nodes render < 500ms" is covered by F3's perf benchmark suite,
// which builds a fixture via the cascade store and times rebuildGraph under
// a real Vue Flow render. 1ms-1000ms threshold accommodates CI runners.
const PERF_BUDGET_MS = Number(process.env.STORYOS_PERF_BUDGET_MS ?? 1000)

describe('CascadeGraph performance', () => {
  it(`empty-state mount < ${PERF_BUDGET_MS}ms (smoke test; 100-node fixture is F3)`, () => {
    setActivePinia(createPinia())
    const start = performance.now()
    mount(CascadeGraph, { props: { slug: 'proj-1' } })
    const elapsed = performance.now() - start
    expect(elapsed).toBeLessThan(PERF_BUDGET_MS)
  })
})
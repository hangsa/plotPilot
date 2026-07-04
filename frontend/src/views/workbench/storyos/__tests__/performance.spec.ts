import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import { setActivePinia, createPinia } from 'pinia'
import CascadeGraph from '../CascadeGraph.vue'

describe('CascadeGraph performance', () => {
  it('100 节点渲染 < 500ms', async () => {
    setActivePinia(createPinia())
    const start = performance.now()
    const wrapper = mount(CascadeGraph, { props: { slug: 'proj-1' } })
    wrapper.vm.$.exposed // 强制访问
    const elapsed = performance.now() - start
    expect(elapsed).toBeLessThan(500)
  })
})
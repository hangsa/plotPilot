import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { setActivePinia, createPinia } from 'pinia'
import { cascadeApi } from '@/api/storyos'

vi.mock('@/api/storyos', () => ({
  cascadeApi: { simulate: vi.fn(), history: vi.fn(), replay: vi.fn() },
  conflictApi: { list: vi.fn(), get: vi.fn(), create: vi.fn(), update: vi.fn(), delete: vi.fn() },
  mysteryApi: { list: vi.fn(), get: vi.fn(), create: vi.fn(), update: vi.fn(), delete: vi.fn() },
  twistApi: { list: vi.fn(), get: vi.fn(), create: vi.fn(), update: vi.fn(), delete: vi.fn() },
  promiseApi: { list: vi.fn(), get: vi.fn(), create: vi.fn(), update: vi.fn(), delete: vi.fn() },
  revealApi: { list: vi.fn(), get: vi.fn(), create: vi.fn(), update: vi.fn(), delete: vi.fn() },
  expectationApi: { list: vi.fn(), get: vi.fn(), create: vi.fn(), update: vi.fn(), delete: vi.fn() },
  goalApi: { list: vi.fn(), get: vi.fn(), create: vi.fn(), update: vi.fn(), delete: vi.fn() },
  foreshadowingApi: { list: vi.fn(), get: vi.fn(), create: vi.fn(), update: vi.fn(), delete: vi.fn() },
}))

import CascadeGraph from '../CascadeGraph.vue'

describe('CascadeGraph', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('点击 Simulate 调用 cascadeApi.simulate', async () => {
    ;(cascadeApi.simulate as any).mockResolvedValue({
      steps: [],
      blockedSteps: [],
      summary: { wouldBlock: false, maxDepthReached: 0, stepsCount: 0, blockedStepsCount: 0, wouldCreateCycle: false },
    })
    const wrapper = mount(CascadeGraph, { props: { slug: 'proj-1' } })
    const setup = wrapper.vm.$.setupState
    setup.triggerForm.sourceAssetId = 'm-1'
    setup.triggerForm.trigger = 'mystery_revealed'
    setup.triggerForm.sourceAssetType = 'mystery'
    await wrapper.find('button.simulate-btn').trigger('click')
    await flushPromises()
    expect(cascadeApi.simulate).toHaveBeenCalled()
  })

  it('渲染 Vue Flow', () => {
    const wrapper = mount(CascadeGraph, { props: { slug: 'proj-1' } })
    expect(wrapper.find('[data-testid="vue-flow"]').exists()).toBe(true)
  })

  it('3 步级联生成 N+1 节点（1 root + N step）+ N 条连边（拓扑链）', async () => {
    ;(cascadeApi.simulate as any).mockResolvedValue({
      steps: [
        { trigger: 'mystery_revealed', sourceAssetId: 'm-1', targetAssetId: 'e-1', newStatus: 'ready_to_fulfill' },
        { trigger: 'expectation_fulfill', sourceAssetId: 'e-1', targetAssetId: 'c-1', newStatus: 'escalated' },
        { trigger: 'conflict_escalate', sourceAssetId: 'c-1', targetAssetId: 'c-2', newStatus: 'escalated' },
      ],
      blockedSteps: [],
      summary: { wouldBlock: false, maxDepthReached: 2, stepsCount: 3, blockedStepsCount: 0, wouldCreateCycle: false },
    })
    const wrapper = mount(CascadeGraph, { props: { slug: 'proj-1' } })
    const setup = wrapper.vm.$.setupState
    setup.triggerForm.sourceAssetId = 'm-1'
    setup.triggerForm.trigger = 'mystery_revealed'
    setup.triggerForm.sourceAssetType = 'mystery'
    await wrapper.find('button.simulate-btn').trigger('click')
    await flushPromises()
    const nodes = wrapper.vm.vueFlowNodes ?? wrapper.vm.$.setupState.vueFlowNodes
    const edges = wrapper.vm.vueFlowEdges ?? wrapper.vm.$.setupState.vueFlowEdges
    expect(nodes).toHaveLength(4)
    expect(edges).toHaveLength(3)
    expect(edges[0].source).toBe('root-m-1')
    expect(edges[0].target).toBe('s0-e-1')
    expect(edges[2].target).toBe('s2-c-2')
  })
})
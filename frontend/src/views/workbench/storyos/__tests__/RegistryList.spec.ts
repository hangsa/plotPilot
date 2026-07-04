import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { setActivePinia, createPinia } from 'pinia'
import { createRouter, createMemoryHistory } from 'vue-router'
import RegistryList from '../RegistryList.vue'
import { useStoryosQueriesStore } from '@/stores/storyos/queries'
import { conflictApi } from '@/api/storyos'

vi.mock('@/api/storyos', () => ({
  conflictApi: { list: vi.fn(), get: vi.fn(), create: vi.fn(), update: vi.fn(), delete: vi.fn() },
  mysteryApi: { list: vi.fn(), get: vi.fn(), create: vi.fn(), update: vi.fn(), delete: vi.fn() },
  twistApi: { list: vi.fn(), get: vi.fn(), create: vi.fn(), update: vi.fn(), delete: vi.fn() },
  promiseApi: { list: vi.fn(), get: vi.fn(), create: vi.fn(), update: vi.fn(), delete: vi.fn() },
  revealApi: { list: vi.fn(), get: vi.fn(), create: vi.fn(), update: vi.fn(), delete: vi.fn() },
  expectationApi: { list: vi.fn(), get: vi.fn(), create: vi.fn(), update: vi.fn(), delete: vi.fn() },
  goalApi: { list: vi.fn(), get: vi.fn(), create: vi.fn(), update: vi.fn(), delete: vi.fn() },
  foreshadowingApi: { list: vi.fn(), get: vi.fn(), create: vi.fn(), update: vi.fn(), delete: vi.fn() },
}))

describe('RegistryList', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  it('默认根据 route param assetType 加载列表', async () => {
    ;(conflictApi.list as any).mockResolvedValue({
      data: [{ id: 'cf-1', description: 'x', status: 'active', createdChapter: 1 }],
      meta: { total: 1, page: 1, pageSize: 20, totalPages: 1, hasNext: false, hasPrev: false },
    })
    const router = createRouter({
      history: createMemoryHistory(),
      routes: [{ path: '/:slug/storyos/:assetType', component: { template: '<div/>' } }],
    })
    await router.push('/proj-1/storyos/conflict')
    await router.isReady()
    const wrapper = mount(RegistryList, {
      global: { plugins: [router] },
    })
    await flushPromises()
    const cards = wrapper.findAllComponents({ name: 'AssetCard' })
    expect(cards.length).toBeGreaterThan(0)
    expect(cards[0].props('asset').id).toBe('cf-1')
  })

  it('点击 AssetCard 打开 RegistryDetailDrawer', async () => {
    ;(conflictApi.list as any).mockResolvedValue({
      data: [{ id: 'cf-1', description: 'x', status: 'active', createdChapter: 1 }],
      meta: { total: 0, page: 1, pageSize: 20, totalPages: 0, hasNext: false, hasPrev: false },
    })
    const router = createRouter({
      history: createMemoryHistory(),
      routes: [{ path: '/:slug/storyos/:assetType', component: { template: '<div/>' } }],
    })
    await router.push('/proj-1/storyos/conflict')
    await router.isReady()
    const wrapper = mount(RegistryList, { global: { plugins: [router] } })
    await flushPromises()
    await wrapper.findComponent({ name: 'AssetCard' }).trigger('click')
    await wrapper.vm.$nextTick()
    expect(wrapper.findComponent({ name: 'RegistryDetailDrawer' }).exists()).toBe(true)
  })

  it('支持 status filter', async () => {
    ;(conflictApi.list as any).mockResolvedValue({ data: [], meta: { total: 0, page: 1, pageSize: 20, totalPages: 0, hasNext: false, hasPrev: false } })
    const router = createRouter({
      history: createMemoryHistory(),
      routes: [{ path: '/:slug/storyos/:assetType', component: { template: '<div/>' } }],
    })
    await router.push('/proj-1/storyos/conflict')
    await router.isReady()
    const wrapper = mount(RegistryList, { global: { plugins: [router] } })
    await flushPromises()
    await wrapper.find('select.status-filter').setValue('active')
    // Allow watch-triggered loadList to run
    await flushPromises()
    expect(conflictApi.list).toHaveBeenCalledWith(
      'proj-1',
      expect.objectContaining({ status: 'active' }),
    )
  })
})
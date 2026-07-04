import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { setActivePinia, createPinia } from 'pinia'
import RegistryDetailDrawer from '../RegistryDetailDrawer.vue'
import { useStoryosQueriesStore } from '@/stores/storyos/queries'

vi.mock('@/stores/storyos/queries', () => ({
  useStoryosQueriesStore: vi.fn(),
}))

describe('RegistryDetailDrawer', () => {
  let mockStore: any

  beforeEach(() => {
    setActivePinia(createPinia())
    mockStore = {
      fetchOne: vi.fn().mockResolvedValue({ id: 'cf-1', description: 'old', status: 'active', createdChapter: 1 }),
      update: vi.fn().mockResolvedValue({ id: 'cf-1', description: 'new', status: 'active', createdChapter: 1 }),
    }
    ;(useStoryosQueriesStore as any).mockReturnValue(mockStore)
  })

  it('renders drawer content when assetId is set', async () => {
    const wrapper = mount(RegistryDetailDrawer, {
      props: { slug: 'proj-1', assetType: 'conflict', assetId: 'cf-1' },
    })
    await flushPromises()
    expect(wrapper.find('.drawer-content').exists()).toBe(true)
  })

  it('save button calls update and emits updated', async () => {
    const wrapper = mount(RegistryDetailDrawer, {
      props: { slug: 'proj-1', assetType: 'conflict', assetId: 'cf-1' },
    })
    await flushPromises()
    await wrapper.find('button.save').trigger('click')
    await flushPromises()
    expect(mockStore.update).toHaveBeenCalled()
    expect(wrapper.emitted('updated')).toBeTruthy()
  })

  it('close button emits close', async () => {
    const wrapper = mount(RegistryDetailDrawer, {
      props: { slug: 'proj-1', assetType: 'conflict', assetId: 'cf-1' },
    })
    await wrapper.find('button.close').trigger('click')
    expect(wrapper.emitted('close')).toBeTruthy()
  })
})

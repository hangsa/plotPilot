import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { setActivePinia, createPinia } from 'pinia'

vi.mock('@/api/storyos', () => ({ sflogApi: { reparse: vi.fn() } }))
import { sflogApi } from '@/api/storyos'
import PredeclaredDiff from '../PredeclaredDiff.vue'

describe('PredeclaredDiff', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('匹配 = 绿色', async () => {
    ;(sflogApi.reparse as any).mockResolvedValue({
      chapterId: 5,
      matchReport: {
        predeclaredTotal: 2, predeclaredImplemented: 1,
        missingChanges: [], unexpectedRecords: [],
        matchRate: 0.5,
      },
    })
    const wrapper = mount(PredeclaredDiff, { props: { slug: 'proj-1', chapterId: 5 } })
    await flushPromises()
    expect(wrapper.find('.match-rate').text()).toContain('50%')
  })

  it('缺失 = 红色', async () => {
    ;(sflogApi.reparse as any).mockResolvedValue({
      chapterId: 5,
      matchReport: {
        predeclaredTotal: 2, predeclaredImplemented: 1,
        missingChanges: [{ assetId: 'm1' }],
        unexpectedRecords: [],
        matchRate: 0.5,
      },
    })
    const wrapper = mount(PredeclaredDiff, { props: { slug: 'proj-1', chapterId: 5 } })
    await flushPromises()
    expect(wrapper.findAll('.diff-missing').length).toBe(1)
  })
})
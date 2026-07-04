import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { setActivePinia, createPinia } from 'pinia'
import { sflogApi } from '@/api/storyos'

vi.mock('@/api/storyos', () => ({ sflogApi: { raw: vi.fn(), reparse: vi.fn() } }))

import SFLogInspector from '../SFLogInspector.vue'

describe('SFLogInspector', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('加载指定章节 raw 文本与 records', async () => {
    ;(sflogApi.raw as any).mockResolvedValue({
      projectId: 'proj-1',
      chapterId: 5,
      rawText: 'before <!-- SF_LOG MYSTERY_CLUE mystery_id="m1" content="x" --> after',
      records: [{ logType: 'mystery_clue', params: { mystery_id: 'm1', content: 'x' }, chapterId: 5, charPosition: 7, assetId: 'm1', raw: '...' }],
      sfLogCount: 1,
    })
    const wrapper = mount(SFLogInspector, { props: { slug: 'proj-1', chapterId: 5 } })
    await flushPromises()
    expect(wrapper.find('.sf-log-raw-text').text()).toContain('SF_LOG')
    expect(wrapper.findAll('.sf-log-record-item').length).toBe(1)
  })

  it('支持切换章节', async () => {
    ;(sflogApi.raw as any).mockResolvedValue({ projectId: 'proj-1', chapterId: 1, rawText: 'x', records: [], sfLogCount: 0 })
    const wrapper = mount(SFLogInspector, { props: { slug: 'proj-1', chapterId: 1 } })
    await wrapper.find('input.chapter-input').setValue('10')
    await wrapper.find('input.chapter-input').trigger('change')
    expect(sflogApi.raw).toHaveBeenCalledWith('proj-1', 10)
  })
})
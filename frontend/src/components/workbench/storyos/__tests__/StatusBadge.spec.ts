import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import StatusBadge from '../StatusBadge.vue'
import type { AssetStatus } from '@/types/storyos'

describe('StatusBadge', () => {
  const cases: Array<[AssetStatus, string]> = [
    ['active', 'badge-blue'],
    ['accumulating', 'badge-blue'],
    ['planted', 'badge-yellow'],
    ['ready_to_fulfill', 'badge-yellow'],
    ['escalated', 'badge-yellow'],
    ['revealed', 'badge-green'],
    ['fulfilled', 'badge-green'],
    ['resolved', 'badge-green'],
    ['abandoned', 'badge-red'],
    ['dead', 'badge-red'],
  ]

  it.each(cases)('status=%s 渲染颜色 class %s', (status, expectedClass) => {
    const wrapper = mount(StatusBadge, { props: { status } })
    expect(wrapper.find(`.${expectedClass}`).exists()).toBe(true)
    expect(wrapper.text()).toBe(status)
  })

  it('支持 size prop', () => {
    const wrapper = mount(StatusBadge, { props: { status: 'active', size: 'small' } })
    expect(wrapper.find('.badge-small').exists()).toBe(true)
  })
})

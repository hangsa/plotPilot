import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import AssetCard from '../AssetCard.vue'

describe('AssetCard', () => {
  const baseAsset = {
    id: 'cf-1',
    description: 'A test conflict',
    status: 'active' as const,
    createdChapter: 5,
  }

  it('renders description and id', () => {
    const wrapper = mount(AssetCard, { props: { asset: baseAsset } })
    expect(wrapper.text()).toContain('A test conflict')
    expect(wrapper.text()).toContain('cf-1')
  })

  it('emits click event with asset when card is clicked', async () => {
    const wrapper = mount(AssetCard, { props: { asset: baseAsset } })
    await wrapper.find('.asset-card').trigger('click')
    expect(wrapper.emitted('click')).toBeTruthy()
    expect(wrapper.emitted('click')![0][0]).toEqual(baseAsset)
  })

  it('applies selected class when selected prop is true', () => {
    const wrapper = mount(AssetCard, { props: { asset: baseAsset, selected: true } })
    expect(wrapper.find('.asset-card').classes()).toContain('selected')
  })
})

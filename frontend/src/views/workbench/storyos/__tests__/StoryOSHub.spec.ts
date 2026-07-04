import { describe, it, expect, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import type { VueWrapper } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createRouter, createMemoryHistory, type Router } from 'vue-router'
import StoryOSHub from '../StoryOSHub.vue'

// vue-i18n is resolved to a stub via vitest.config.ts alias (app does not
// install vue-i18n; templates that call $t use the per-test mocks entry
// below, which returns the key string back).

function mountHub(router: Router) {
  return mount(StoryOSHub, {
    props: { slug: 'proj-1' },
    global: {
      plugins: [router],
      mocks: { $t: (k: string) => k },
    },
  }) as VueWrapper
}

describe('StoryOSHub', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('渲染左侧 8 registry 导航 + 右侧 router-view', () => {
    const router = createRouter({
      history: createMemoryHistory(),
      routes: [{ path: '/:pathMatch(.*)*', component: { template: '<div/>' } }],
    })
    const wrapper = mountHub(router)
    expect(wrapper.find('.storyos-sidebar').exists()).toBe(true)
    expect(wrapper.find('.storyos-main').exists()).toBe(true)
    const navItems = wrapper.findAll('.storyos-sidebar-item')
    expect(navItems).toHaveLength(8)
  })

  it('点击 navigation 切换路由', async () => {
    const router = createRouter({
      history: createMemoryHistory(),
      routes: [
        // Component pushes by route name, so the named route must exist.
        {
          path: '/:slug/storyos',
          name: 'WorkbenchStoryosRegistryList',
          component: { template: '<div class="placeholder"/>' },
        },
        {
          path: '/:slug/storyos/cascade',
          name: 'WorkbenchStoryosCascade',
          component: { template: '<div class="cascade"/>' },
        },
      ],
    })
    await router.push('/proj-1/storyos')
    await router.isReady()
    const wrapper = mountHub(router)
    // Observability nav uses a sibling class (.storyos-sidebar-link) so that
    // the 8-registry count test stays exact.
    await wrapper.find('[data-asset="cascade"]').trigger('click')
    // router.push resolves on a microtask; wait one full tick + flush queue.
    await wrapper.vm.$nextTick()
    await new Promise((r) => setTimeout(r, 0))
    expect(router.currentRoute.value.path).toBe('/proj-1/storyos/cascade')
  })

  it('显示当前项目 ID', () => {
    const router = createRouter({
      history: createMemoryHistory(),
      routes: [{ path: '/:pathMatch(.*)*', component: { template: '<div/>' } }],
    })
    const wrapper = mountHub(router)
    expect(wrapper.find('.storyos-project-id').text()).toContain('proj-1')
  })
})
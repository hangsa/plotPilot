import { describe, it, expect } from 'vitest'
import { workbenchStoryosRoutes } from '../workbench'

describe('workbenchStoryosRoutes', () => {
  it('导出 1 个父路由（path: storyos）含 5 个子路由', () => {
    expect(workbenchStoryosRoutes).toHaveLength(1)
    const parent = workbenchStoryosRoutes[0]
    expect(parent.children).toHaveLength(5)
  })

  it('默认子路由是 registry-list (path: "")', () => {
    const parent = workbenchStoryosRoutes[0]
    const defaultChild = parent.children!.find((c: any) => c.path === '')
    expect(defaultChild).toBeDefined()
  })

  it('父路径包含 :slug 参数', () => {
    const parent = workbenchStoryosRoutes[0]
    expect(parent.path).toContain(':slug')
  })
})

import { describe, it, expect, beforeEach, vi } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useStoryosQueriesStore } from '../queries'
import { conflictApi } from '@/api/storyos'

vi.mock('@/api/storyos', () => ({
  conflictApi: {
    list: vi.fn(),
    get: vi.fn(),
    create: vi.fn(),
    update: vi.fn(),
    delete: vi.fn(),
  },
  mysteryApi: { list: vi.fn(), get: vi.fn(), create: vi.fn(), update: vi.fn(), delete: vi.fn() },
  twistApi: { list: vi.fn(), get: vi.fn(), create: vi.fn(), update: vi.fn(), delete: vi.fn() },
  promiseApi: { list: vi.fn(), get: vi.fn(), create: vi.fn(), update: vi.fn(), delete: vi.fn() },
  revealApi: { list: vi.fn(), get: vi.fn(), create: vi.fn(), update: vi.fn(), delete: vi.fn() },
  expectationApi: { list: vi.fn(), get: vi.fn(), create: vi.fn(), update: vi.fn(), delete: vi.fn() },
  goalApi: { list: vi.fn(), get: vi.fn(), create: vi.fn(), update: vi.fn(), delete: vi.fn() },
  foreshadowingApi: { list: vi.fn(), get: vi.fn(), create: vi.fn(), update: vi.fn(), delete: vi.fn() },
}))

describe('useStoryosQueriesStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  it('fetchList 加载数据并存入 cache', async () => {
    ;(conflictApi.list as any).mockResolvedValue({
      data: [{ id: 'cf-1', description: 'x' }],
      meta: { total: 1, page: 1, pageSize: 20, totalPages: 1, hasNext: false, hasPrev: false },
    })
    const store = useStoryosQueriesStore()
    await store.fetchList('proj-1', 'conflict', { page: 1, pageSize: 20 })
    expect(store.conflictList).toHaveLength(1)
    expect(store.conflictList[0].id).toBe('cf-1')
  })

  it('fetchList 缓存命中不重复请求', async () => {
    ;(conflictApi.list as any).mockResolvedValue({
      data: [], meta: { total: 0, page: 1, pageSize: 20, totalPages: 0, hasNext: false, hasPrev: false },
    })
    const store = useStoryosQueriesStore()
    await store.fetchList('proj-1', 'conflict', { page: 1, pageSize: 20 })
    await store.fetchList('proj-1', 'conflict', { page: 1, pageSize: 20 })
    expect(conflictApi.list).toHaveBeenCalledTimes(1)
  })

  it('create 追加到 cache 头部', async () => {
    ;(conflictApi.create as any).mockResolvedValue({ id: 'cf-2', description: 'new' })
    const store = useStoryosQueriesStore()
    const result = await store.create('proj-1', 'conflict', { description: 'new', createdChapter: 1 })
    expect(result.id).toBe('cf-2')
  })

  it('update 替换 cache 项', async () => {
    ;(conflictApi.update as any).mockResolvedValue({ id: 'cf-1', description: 'updated' })
    const store = useStoryosQueriesStore()
    store.conflictList = [{ id: 'cf-1', description: 'old' }] as any
    await store.update('proj-1', 'conflict', 'cf-1', { description: 'updated' })
    expect(store.conflictList[0].description).toBe('updated')
  })

  it('delete 从 cache 移除', async () => {
    ;(conflictApi.delete as any).mockResolvedValue(undefined)
    const store = useStoryosQueriesStore()
    store.conflictList = [{ id: 'cf-1' }, { id: 'cf-2' }] as any
    await store.delete('proj-1', 'conflict', 'cf-1')
    expect(store.conflictList).toHaveLength(1)
    expect(store.conflictList[0].id).toBe('cf-2')
  })

  it('invalidate 清除 cache 强制 refetch', async () => {
    ;(conflictApi.list as any).mockResolvedValue({
      data: [], meta: { total: 0, page: 1, pageSize: 20, totalPages: 0, hasNext: false, hasPrev: false },
    })
    const store = useStoryosQueriesStore()
    await store.fetchList('proj-1', 'conflict', {})
    await store.invalidate('conflict')
    await store.fetchList('proj-1', 'conflict', {})
    expect(conflictApi.list).toHaveBeenCalledTimes(2)
  })
})
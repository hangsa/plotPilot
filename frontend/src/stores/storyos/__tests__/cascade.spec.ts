import { describe, it, expect, beforeEach, vi } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useStoryosCascadeStore } from '../cascade'
import { cascadeApi } from '@/api/storyos'
import { useStoryosQueriesStore } from '../queries'

vi.mock('@/api/storyos', () => ({
  cascadeApi: {
    simulate: vi.fn(),
    replay: vi.fn(),
    history: vi.fn(),
  },
  // queries store pulls these via API_MAP
  conflictApi: { list: vi.fn(), get: vi.fn(), create: vi.fn(), update: vi.fn(), delete: vi.fn() },
  mysteryApi: { list: vi.fn(), get: vi.fn(), create: vi.fn(), update: vi.fn(), delete: vi.fn() },
  twistApi: { list: vi.fn(), get: vi.fn(), create: vi.fn(), update: vi.fn(), delete: vi.fn() },
  promiseApi: { list: vi.fn(), get: vi.fn(), create: vi.fn(), update: vi.fn(), delete: vi.fn() },
  revealApi: { list: vi.fn(), get: vi.fn(), create: vi.fn(), update: vi.fn(), delete: vi.fn() },
  expectationApi: { list: vi.fn(), get: vi.fn(), create: vi.fn(), update: vi.fn(), delete: vi.fn() },
  goalApi: { list: vi.fn(), get: vi.fn(), create: vi.fn(), update: vi.fn(), delete: vi.fn() },
  foreshadowingApi: { list: vi.fn(), get: vi.fn(), create: vi.fn(), update: vi.fn(), delete: vi.fn() },
}))

describe('useStoryosCascadeStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  it('simulate 返回结果并保存到 lastSimulation', async () => {
    const fakeResponse = {
      steps: [],
      blockedSteps: [],
      summary: { wouldBlock: false, maxDepthReached: 0, stepsCount: 0, blockedStepsCount: 0, wouldCreateCycle: false },
    }
    ;(cascadeApi.simulate as any).mockResolvedValue(fakeResponse)
    const store = useStoryosCascadeStore()
    const result = await store.simulate('proj-1', {
      trigger: 'mystery_revealed',
      sourceAssetType: 'mystery',
      sourceAssetId: 'm-1',
    })
    expect(result).toEqual(fakeResponse)
    expect(store.lastSimulation).toEqual(fakeResponse)
    expect(store.isSimulating).toBe(false)
  })

  it('replay 调用 queriesStore.invalidate()', async () => {
    ;(cascadeApi.replay as any).mockResolvedValue({ bridgeId: 'br-1', status: 'replayed' })
    const cascadeStore = useStoryosCascadeStore()
    const queriesStore = useStoryosQueriesStore()

    // populate listCache for conflict and mystery
    queriesStore.listCache.set('proj-1:conflict:{}', { data: [], meta: {} })
    queriesStore.listCache.set('proj-1:mystery:{}', { data: [], meta: {} })

    await cascadeStore.replay('proj-1', 'br-1', 'manual')

    // invalidate() with no arg clears all
    expect(queriesStore.listCache.size).toBe(0)
  })

  it('loadHistory 保存到 history 数组', async () => {
    const fakeHistory = {
      data: [
        { bridgeId: 'br-1', ts: '2026-07-04T10:00:00Z' },
        { bridgeId: 'br-2', ts: '2026-07-04T11:00:00Z' },
      ],
      meta: { total: 2, page: 1, pageSize: 50, totalPages: 1, hasNext: false, hasPrev: false },
    }
    ;(cascadeApi.history as any).mockResolvedValue(fakeHistory)
    const store = useStoryosCascadeStore()
    const result = await store.loadHistory('proj-1', 50)
    expect(store.history).toHaveLength(2)
    expect(store.history[0].bridgeId).toBe('br-1')
    expect(result).toEqual(fakeHistory)
  })
})
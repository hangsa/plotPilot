import { describe, it, expect, vi, beforeEach } from 'vitest'
import { cascadeApi } from '../cascade'
import { apiClient } from '../http'

vi.mock('../http', () => ({
  apiClient: {
    get: vi.fn(),
    post: vi.fn(),
    patch: vi.fn(),
    delete: vi.fn(),
  },
}))

describe('cascadeApi', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('simulate POST 触发器与 source 字段', async () => {
    ;(apiClient.post as any).mockResolvedValue({
      steps: [], blockedSteps: [], summary: { wouldBlock: false, maxDepthReached: 0, stepsCount: 0, blockedStepsCount: 0, wouldCreateCycle: false },
    })
    await cascadeApi.simulate('proj-1', {
      trigger: 'mystery_revealed',
      sourceAssetType: 'mystery',
      sourceAssetId: 'm-1',
      proposedNewStatus: 'revealed',
      maxDepth: 3,
    })
    expect(apiClient.post).toHaveBeenCalledWith(
      '/api/v1/storyos/proj-1/cascade/simulate',
      expect.objectContaining({
        trigger: 'mystery_revealed',
        sourceAssetType: 'mystery',
        sourceAssetId: 'm-1',
        proposedNewStatus: 'revealed',
        maxDepth: 3,
      }),
    )
  })

  it('replay POST bridge id 与可选 notes', async () => {
    ;(apiClient.post as any).mockResolvedValue({ bridgeId: 'br-1', status: 'replayed' })
    await cascadeApi.replay('proj-1', 'br-1', 'manual-replay')
    expect(apiClient.post).toHaveBeenCalledWith(
      '/api/v1/storyos/proj-1/cascade/replay/br-1',
      { notes: 'manual-replay' },
    )
  })

  it('history GET 默认 limit=50', async () => {
    ;(apiClient.get as any).mockResolvedValue({ data: [], meta: { total: 0 } })
    await cascadeApi.history('proj-1')
    expect(apiClient.get).toHaveBeenCalledWith(
      '/api/v1/storyos/proj-1/cascade/history',
      { params: { limit: 50 } },
    )
  })

  it('history GET 支持自定义 limit', async () => {
    ;(apiClient.get as any).mockResolvedValue({ data: [], meta: { total: 0 } })
    await cascadeApi.history('proj-1', 10)
    expect(apiClient.get).toHaveBeenCalledWith(
      '/api/v1/storyos/proj-1/cascade/history',
      { params: { limit: 10 } },
    )
  })
})
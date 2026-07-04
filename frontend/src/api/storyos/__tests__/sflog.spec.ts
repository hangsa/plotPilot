import { describe, it, expect, vi, beforeEach } from 'vitest'
import { sflogApi } from '../sflog'
import { apiClient } from '../http'

vi.mock('../http', () => ({
  apiClient: {
    get: vi.fn(),
    post: vi.fn(),
    patch: vi.fn(),
    delete: vi.fn(),
  },
}))

describe('sflogApi', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('raw GET chapter 参数', async () => {
    ;(apiClient.get as any).mockResolvedValue({
      projectId: 'proj-1',
      chapterId: 5,
      rawText: '',
      records: [],
      sfLogCount: 0,
    })
    await sflogApi.raw('proj-1', 5)
    expect(apiClient.get).toHaveBeenCalledWith(
      '/api/v1/storyos/proj-1/sflog/raw',
      { params: { chapter: 5 } },
    )
  })

  it('reparse POST 路径携带 chapterId', async () => {
    ;(apiClient.post as any).mockResolvedValue({
      projectId: 'proj-1',
      chapterId: 5,
      parsedCount: 0,
      formatErrors: [],
      matchReport: {
        predeclaredTotal: 0,
        predeclaredImplemented: 0,
        missingChanges: [],
        unexpectedRecords: [],
        matchRate: 1,
      },
    })
    await sflogApi.reparse('proj-1', 5)
    expect(apiClient.post).toHaveBeenCalledWith(
      '/api/v1/storyos/proj-1/sflog/reparse/5',
    )
  })
})
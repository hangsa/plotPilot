import { describe, it, expect, beforeEach, vi } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useStoryosSflogStore } from '../sflog'
import { sflogApi } from '@/api/storyos'

vi.mock('@/api/storyos', () => ({
  sflogApi: {
    raw: vi.fn(),
    reparse: vi.fn(),
  },
}))

describe('useStoryosSflogStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  it('loadRaw 保存 raw response', async () => {
    const fakeRaw = {
      projectId: 'proj-1',
      chapterId: 5,
      rawText: 'SF-LOG character_emotion: x = happy',
      records: [
        { logType: 'character_emotion', params: { x: 'happy' }, raw: 'SF-LOG character_emotion: x = happy', chapterId: 5, charPosition: 0, assetId: null },
      ],
      sfLogCount: 1,
    }
    ;(sflogApi.raw as any).mockResolvedValue(fakeRaw)
    const store = useStoryosSflogStore()
    await store.loadRaw('proj-1', 5)
    expect(store.currentRaw).toEqual(fakeRaw)
    expect(store.isLoading).toBe(false)
  })

  it('reparse 保存 reparse response', async () => {
    const fakeReparse = {
      projectId: 'proj-1',
      chapterId: 5,
      parsedCount: 3,
      formatErrors: [],
      matchReport: {
        predeclaredTotal: 2,
        predeclaredImplemented: 2,
        missingChanges: [],
        unexpectedRecords: [],
        matchRate: 1,
      },
    }
    ;(sflogApi.reparse as any).mockResolvedValue(fakeReparse)
    const store = useStoryosSflogStore()
    await store.reparse('proj-1', 5)
    expect(store.currentReparse).toEqual(fakeReparse)
    expect(store.isLoading).toBe(false)
  })
})
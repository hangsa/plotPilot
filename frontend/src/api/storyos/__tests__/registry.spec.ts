import { describe, it, expect, vi, beforeEach } from 'vitest'
import { conflictApi } from '../registry'
import { apiClient } from '../http'

vi.mock('../http', () => ({
  apiClient: {
    get: vi.fn(),
    post: vi.fn(),
    patch: vi.fn(),
    delete: vi.fn(),
  },
}))

describe('conflictApi', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('list 调用正确路径与 query params', async () => {
    ;(apiClient.get as any).mockResolvedValue({ data: [], meta: { total: 0 } })
    await conflictApi.list('proj-1', { status: 'active', page: 1, pageSize: 20 })
    expect(apiClient.get).toHaveBeenCalledWith(
      '/api/v1/storyos/proj-1/conflict',
      { params: { status: 'active', page: 1, page_size: 20 } },
    )
  })

  it('get 调用正确路径', async () => {
    ;(apiClient.get as any).mockResolvedValue({ data: { id: 'cf-1' } })
    await conflictApi.get('proj-1', 'cf-1')
    expect(apiClient.get).toHaveBeenCalledWith('/api/v1/storyos/proj-1/conflict/cf-1')
  })

  it('create POST body', async () => {
    ;(apiClient.post as any).mockResolvedValue({ data: { id: 'cf-1' } })
    await conflictApi.create('proj-1', {
      description: 'x',
      createdChapter: 1,
      status: 'active',
      intensity: 50,
    })
    expect(apiClient.post).toHaveBeenCalledWith(
      '/api/v1/storyos/proj-1/conflict',
      expect.objectContaining({ description: 'x' }),
    )
  })

  it('update PATCH 部分字段', async () => {
    ;(apiClient.patch as any).mockResolvedValue({ data: { id: 'cf-1' } })
    await conflictApi.update('proj-1', 'cf-1', { status: 'escalated' })
    expect(apiClient.patch).toHaveBeenCalledWith(
      '/api/v1/storyos/proj-1/conflict/cf-1',
      { status: 'escalated' },
    )
  })

  it('delete 返回 204 不解析 body', async () => {
    ;(apiClient.delete as any).mockResolvedValue({ status: 204 })
    await conflictApi.delete('proj-1', 'cf-1')
    expect(apiClient.delete).toHaveBeenCalledWith('/api/v1/storyos/proj-1/conflict/cf-1')
  })
})
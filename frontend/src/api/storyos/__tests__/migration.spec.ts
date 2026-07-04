import { describe, it, expect, vi, beforeEach } from 'vitest'
import { migrationApi } from '../migration'
import { apiClient } from '../http'

vi.mock('../http', () => ({
  apiClient: {
    get: vi.fn(),
    post: vi.fn(),
    patch: vi.fn(),
    delete: vi.fn(),
  },
}))

function axiosError(status: number): Error {
  const err: any = new Error(`Request failed with status ${status}`)
  err.response = { status }
  err.isAxiosError = true
  return err
}

describe('migrationApi', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('preview 成功路径 POST 正确', async () => {
    ;(apiClient.post as any).mockResolvedValue({
      total: 10, scanned: 10, migratable: 7, skipped: 2, invalid: 1, sampleErrors: [],
    })
    await migrationApi.preview('proj-1')
    expect(apiClient.post).toHaveBeenCalledWith('/api/v1/storyos/proj-1/migration/preview')
  })

  it('preview 501 返回零值 envelope', async () => {
    ;(apiClient.post as any).mockRejectedValue(axiosError(501))
    const result = await migrationApi.preview('proj-1')
    expect(result).toEqual({
      total: 0, scanned: 0, migratable: 0, skipped: 0, invalid: 0, sampleErrors: [],
    })
  })

  it('execute 成功路径 POST body', async () => {
    ;(apiClient.post as any).mockResolvedValue({
      migrationId: 'mig-1',
      status: 'completed',
      batchesTotal: 2, batchesDone: 2, errors: [],
    })
    await migrationApi.execute('proj-1', { batchSize: 50, dryRun: false })
    expect(apiClient.post).toHaveBeenCalledWith(
      '/api/v1/storyos/proj-1/migration/execute',
      { batchSize: 50, dryRun: false },
    )
  })

  it('execute 501 返回 pending 占位', async () => {
    ;(apiClient.post as any).mockRejectedValue(axiosError(501))
    const result = await migrationApi.execute('proj-1', { batchSize: 50 })
    expect(result).toEqual({
      migrationId: 'pending-1e',
      status: 'pending',
      batchesTotal: 0, batchesDone: 0, errors: [],
    })
  })

  it('preview 非 501 错误透传', async () => {
    ;(apiClient.post as any).mockRejectedValue(axiosError(500))
    await expect(migrationApi.preview('proj-1')).rejects.toBeDefined()
  })

  it('execute 非 501 错误透传', async () => {
    ;(apiClient.post as any).mockRejectedValue(axiosError(403))
    await expect(migrationApi.execute('proj-1', {})).rejects.toBeDefined()
  })
})
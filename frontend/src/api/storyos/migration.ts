import { apiClient } from './http'
import type {
  MigrationPreviewResponse, MigrationExecuteRequest, MigrationExecuteResponse,
} from '@/types/storyos'
import type { AxiosError } from 'axios'

export const migrationApi = {
  async preview(projectId: string): Promise<MigrationPreviewResponse> {
    try {
      const body = (await apiClient.post(
        `/api/v1/storyos/${projectId}/migration/preview`,
      )) as MigrationPreviewResponse
      return body
    } catch (e) {
      const err = e as AxiosError<{ error: { message: string } }>
      if (err.response?.status === 501) {
        return {
          total: 0, scanned: 0, migratable: 0, skipped: 0, invalid: 0, sampleErrors: [],
        }
      }
      throw e
    }
  },

  async execute(projectId: string, req: MigrationExecuteRequest = {}): Promise<MigrationExecuteResponse> {
    try {
      const body = (await apiClient.post(
        `/api/v1/storyos/${projectId}/migration/execute`,
        req,
      )) as MigrationExecuteResponse
      return body
    } catch (e) {
      const err = e as AxiosError
      if (err.response?.status === 501) {
        return {
          migrationId: 'pending-1e',
          status: 'pending',
          batchesTotal: 0, batchesDone: 0, errors: [],
        }
      }
      throw e
    }
  },
}
import { apiClient } from './http'
import type {
  CascadeSimulateRequest, CascadeSimulateResponse,
  ListResponse,
} from '@/types/storyos'

export const cascadeApi = {
  async simulate(projectId: string, req: CascadeSimulateRequest): Promise<CascadeSimulateResponse> {
    const body = (await apiClient.post(
      `/api/v1/storyos/${projectId}/cascade/simulate`,
      req,
    )) as CascadeSimulateResponse
    return body
  },

  async replay(projectId: string, bridgeId: string, notes?: string): Promise<{ bridgeId: string; status: string }> {
    const body = (await apiClient.post(
      `/api/v1/storyos/${projectId}/cascade/replay/${bridgeId}`,
      { notes },
    )) as { bridgeId: string; status: string }
    return body
  },

  async history(projectId: string, limit = 50): Promise<ListResponse<unknown>> {
    const body = (await apiClient.get(
      `/api/v1/storyos/${projectId}/cascade/history`,
      { params: { limit } },
    )) as ListResponse<unknown>
    return body
  },
}
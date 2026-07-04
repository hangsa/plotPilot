import { apiClient } from './http'
import type { HealthResponse, StoryOSMetrics } from '@/types/storyos'

export const healthApi = {
  async check(projectId: string): Promise<HealthResponse> {
    const body = (await apiClient.get(
      `/api/v1/storyos/${projectId}/health`,
    )) as HealthResponse
    return body
  },

  async metrics(projectId: string): Promise<StoryOSMetrics> {
    const body = (await apiClient.get(
      `/api/v1/storyos/${projectId}/metrics`,
    )) as StoryOSMetrics
    return body
  },
}
import { apiClient } from './http'
import type { SFLogRawResponse, SFLogReparseResponse } from '@/types/storyos'

export const sflogApi = {
  async raw(projectId: string, chapter: number): Promise<SFLogRawResponse> {
    const body = (await apiClient.get(
      `/api/v1/storyos/${projectId}/sflog/raw`,
      { params: { chapter } },
    )) as SFLogRawResponse
    return body
  },

  async reparse(projectId: string, chapterId: number): Promise<SFLogReparseResponse> {
    const body = (await apiClient.post(
      `/api/v1/storyos/${projectId}/sflog/reparse/${chapterId}`,
    )) as SFLogReparseResponse
    return body
  },
}
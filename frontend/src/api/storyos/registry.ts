import { apiClient } from './http'
import type {
  AssetType, ConflictAsset, MysteryAsset, TwistAsset, PromiseAsset,
  RevealAsset, ExpectationAsset, GoalAsset, ForeshadowingAsset,
  ListResponse,
} from '@/types/storyos'

interface Envelope<T> {
  data: T
  meta?: unknown
}

function buildCRUDClient<T extends { id: string }>(assetType: AssetType) {
  const base = (projectId: string) => `/api/v1/storyos/${projectId}/${assetType}`

  return {
    async list(
      projectId: string,
      params?: { status?: string; page?: number; pageSize?: number },
    ): Promise<ListResponse<T>> {
      const body = (await apiClient.get(base(projectId), {
        params: {
          status: params?.status,
          page: params?.page ?? 1,
          page_size: params?.pageSize ?? 20,
        },
      })) as Envelope<T[]>
      return body as unknown as ListResponse<T>
    },

    async get(projectId: string, assetId: string): Promise<T> {
      const body = (await apiClient.get(`${base(projectId)}/${assetId}`)) as Envelope<T>
      return (body.data ?? (body as unknown as T))
    },

    async create(projectId: string, payload: Partial<T>): Promise<T> {
      const body = (await apiClient.post(base(projectId), payload)) as Envelope<T>
      return (body.data ?? (body as unknown as T))
    },

    async update(projectId: string, assetId: string, payload: Partial<T>): Promise<T> {
      const body = (await apiClient.patch(`${base(projectId)}/${assetId}`, payload)) as Envelope<T>
      return (body.data ?? (body as unknown as T))
    },

    async delete(projectId: string, assetId: string): Promise<void> {
      await apiClient.delete(`${base(projectId)}/${assetId}`)
    },
  }
}

export const conflictApi = buildCRUDClient<ConflictAsset>('conflict')
export const mysteryApi = buildCRUDClient<MysteryAsset>('mystery')
export const twistApi = buildCRUDClient<TwistAsset>('twist')
export const promiseApi = buildCRUDClient<PromiseAsset>('promise')
export const revealApi = buildCRUDClient<RevealAsset>('reveal')
export const expectationApi = buildCRUDClient<ExpectationAsset>('expectation')
export const goalApi = buildCRUDClient<GoalAsset>('goal')
export const foreshadowingApi = buildCRUDClient<ForeshadowingAsset>('foreshadowing')
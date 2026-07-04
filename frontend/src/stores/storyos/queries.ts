import { defineStore } from 'pinia'
import { ref } from 'vue'
import {
  conflictApi, mysteryApi, twistApi, promiseApi,
  revealApi, expectationApi, goalApi, foreshadowingApi,
} from '@/api/storyos'
import type { AssetType } from '@/types/storyos'

const API_MAP = {
  conflict: conflictApi,
  mystery: mysteryApi,
  twist: twistApi,
  promise: promiseApi,
  reveal: revealApi,
  expectation: expectationApi,
  goal: goalApi,
  foreshadowing: foreshadowingApi,
} as const

type ListParams = { status?: string; page?: number; pageSize?: number }

interface ListResult {
  data: unknown[]
  meta: unknown
}

interface DetailResult {
  id: string
  [key: string]: unknown
}

export const useStoryosQueriesStore = defineStore('storyos-queries', () => {
  const conflictList = ref<unknown[]>([])
  const mysteryList = ref<unknown[]>([])
  const twistList = ref<unknown[]>([])
  const promiseList = ref<unknown[]>([])
  const revealList = ref<unknown[]>([])
  const expectationList = ref<unknown[]>([])
  const goalList = ref<unknown[]>([])
  const foreshadowingList = ref<unknown[]>([])

  const detailCache = ref<Map<string, DetailResult>>(new Map())
  const isLoading = ref(false)
  const error = ref<string | null>(null)
  const listCache = ref<Map<string, ListResult>>(new Map())

  function _listRef(assetType: AssetType) {
    const refs: Record<AssetType, { value: unknown[] }> = {
      conflict: conflictList,
      mystery: mysteryList,
      twist: twistList,
      promise: promiseList,
      reveal: revealList,
      expectation: expectationList,
      goal: goalList,
      foreshadowing: foreshadowingList,
    }
    return refs[assetType]
  }

  function _cacheKey(projectId: string, assetType: AssetType, params: ListParams): string {
    return `${projectId}:${assetType}:${JSON.stringify(params)}`
  }

  async function fetchList(
    projectId: string,
    assetType: AssetType,
    params: ListParams = {},
  ): Promise<ListResult> {
    const key = _cacheKey(projectId, assetType, params)
    const cached = listCache.value.get(key)
    if (cached) {
      _listRef(assetType).value = cached.data
      return cached
    }
    isLoading.value = true
    try {
      const result = (await API_MAP[assetType].list(projectId, params)) as unknown as ListResult
      _listRef(assetType).value = result.data
      listCache.value.set(key, result)
      return result
    } finally {
      isLoading.value = false
    }
  }

  async function fetchOne(
    projectId: string,
    assetType: AssetType,
    assetId: string,
  ): Promise<DetailResult> {
    const key = `${projectId}:${assetType}:${assetId}`
    const cached = detailCache.value.get(key)
    if (cached) {
      return cached
    }
    const item = (await API_MAP[assetType].get(projectId, assetId)) as unknown as DetailResult
    detailCache.value.set(key, item)
    return item
  }

  async function create(
    projectId: string,
    assetType: AssetType,
    payload: Record<string, unknown>,
  ): Promise<DetailResult> {
    const created = (await API_MAP[assetType].create(projectId, payload)) as unknown as DetailResult
    const ref = _listRef(assetType)
    ref.value = [created, ...ref.value]
    invalidate(assetType)
    return created
  }

  async function update(
    projectId: string,
    assetType: AssetType,
    assetId: string,
    payload: Record<string, unknown>,
  ): Promise<DetailResult> {
    const updated = (await API_MAP[assetType].update(projectId, assetId, payload)) as unknown as DetailResult
    const list = _listRef(assetType).value as Array<{ id: string }>
    const idx = list.findIndex((x) => x.id === assetId)
    if (idx >= 0) {
      list[idx] = updated
    }
    detailCache.value.set(`${projectId}:${assetType}:${assetId}`, updated)
    return updated
  }

  async function deleteOne(
    projectId: string,
    assetType: AssetType,
    assetId: string,
  ): Promise<void> {
    await API_MAP[assetType].delete(projectId, assetId)
    const list = _listRef(assetType).value as Array<{ id: string }>
    _listRef(assetType).value = list.filter((x) => x.id !== assetId)
    detailCache.value.delete(`${projectId}:${assetType}:${assetId}`)
  }

  function invalidate(assetType?: AssetType): void {
    if (assetType) {
      for (const key of listCache.value.keys()) {
        if (key.includes(`:${assetType}:`)) {
          listCache.value.delete(key)
        }
      }
    } else {
      listCache.value.clear()
    }
  }

  return {
    conflictList,
    mysteryList,
    twistList,
    promiseList,
    revealList,
    expectationList,
    goalList,
    foreshadowingList,
    detailCache,
    isLoading,
    error,
    listCache,
    fetchList,
    fetchOne,
    create,
    update,
    delete: deleteOne,
    invalidate,
  }
})
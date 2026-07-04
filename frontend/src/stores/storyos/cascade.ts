import { defineStore } from 'pinia'
import { ref } from 'vue'
import { cascadeApi } from '@/api/storyos'
import type {
  CascadeSimulateRequest,
  CascadeSimulateResponse,
  ListResponse,
} from '@/types/storyos'
import { useStoryosQueriesStore } from './queries'

export const useStoryosCascadeStore = defineStore('storyos-cascade', () => {
  const lastSimulation = ref<CascadeSimulateResponse | null>(null)
  const history = ref<unknown[]>([])
  const isSimulating = ref(false)
  const error = ref<string | null>(null)

  async function simulate(
    projectId: string,
    req: CascadeSimulateRequest,
  ): Promise<CascadeSimulateResponse> {
    isSimulating.value = true
    try {
      const result = await cascadeApi.simulate(projectId, req)
      lastSimulation.value = result
      return result
    } finally {
      isSimulating.value = false
    }
  }

  async function replay(
    projectId: string,
    bridgeId: string,
    notes?: string,
  ): Promise<{ bridgeId: string; status: string }> {
    const result = await cascadeApi.replay(projectId, bridgeId, notes)
    useStoryosQueriesStore().invalidate()
    return result
  }

  async function loadHistory(
    projectId: string,
    limit = 50,
  ): Promise<ListResponse<unknown>> {
    const result = await cascadeApi.history(projectId, limit)
    history.value = result.data
    return result
  }

  return {
    lastSimulation,
    history,
    isSimulating,
    error,
    simulate,
    replay,
    loadHistory,
  }
})